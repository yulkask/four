using System.Collections.Concurrent;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text;

namespace P2PChat;

// Узел из таблицы активных участников. Ключ таблицы - IP отправителя.
sealed class Peer
{
    public required string Name;
    public DateTime LastSeen;
}

static class Program
{
    // Константы протокола, общие для всей аудитории.
    const int Port = 50000;
    static readonly IPAddress BroadcastAddress = IPAddress.Parse("255.255.255.255");
    const int MaxPacketBytes = 1024;
    const int MaxNameLength = 20;
    static readonly TimeSpan BeaconInterval = TimeSpan.FromSeconds(10);
    static readonly TimeSpan PeerTimeout = TimeSpan.FromSeconds(45);
    static readonly TimeSpan LocalAddressesRefresh = TimeSpan.FromSeconds(10);

    const string LogFile = "p2p_chat.log";

    // Строгий декодер: на некорректном UTF-8 бросает исключение, и пакет игнорируется.
    static readonly UTF8Encoding StrictUtf8 = new(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true);

    static readonly Dictionary<IPAddress, Peer> Peers = new();
    static readonly ConcurrentQueue<string> InputLines = new();
    static readonly object ConsoleLock = new();

    static HashSet<IPAddress> _localAddresses = new();
    static StreamWriter _log = null!;
    static Socket _socket = null!;
    static string _myName = "";
    static volatile bool _running = true;

    static int Main(string[] args)
    {
        Console.InputEncoding = Encoding.UTF8;
        Console.OutputEncoding = Encoding.UTF8;

        _myName = args.Length > 0 ? string.Join(' ', args) : "";
        while (!IsValidName(_myName.Trim()))
        {
            if (_myName.Length > 0)
                Console.WriteLine($"Некорректное имя: 1-{MaxNameLength} символов, без '|' и переводов строки.");
            Console.Write("Введите имя: ");
            string? line = Console.ReadLine();
            if (line == null)
                return 1;
            _myName = line;
        }
        _myName = _myName.Trim();

        _log = new StreamWriter(LogFile, append: true, new UTF8Encoding(false)) { AutoFlush = true };
        WriteLog($"==== Запуск, имя: {_myName}, порт: {Port} ====");

        _socket = CreateSocket();
        RefreshLocalAddresses();

        Console.CancelKeyPress += (_, e) =>
        {
            // Ctrl+C: не убиваем процесс сразу, а даём главному циклу отправить BYE.
            e.Cancel = true;
            _running = false;
        };
        StartInputThread();

        Print($"Вы вошли в чат как {_myName}. Порт {Port}.");
        Print("Введите сообщение и нажмите Enter. Команды: /list - список узлов, /quit - выход.");

        Send("DISCOVER", "");
        DateTime nextBeacon = DateTime.Now + BeaconInterval;
        DateTime nextAddressRefresh = DateTime.Now + LocalAddressesRefresh;

        while (_running)
        {
            // Ждём данных на сокете не дольше 100 мс, чтобы успевать обрабатывать ввод и таймеры.
            if (_socket.Poll(100_000, SelectMode.SelectRead))
                ReceiveAll();

            while (InputLines.TryDequeue(out string? line))
                HandleInput(line);

            DateTime now = DateTime.Now;
            if (now >= nextBeacon)
            {
                Send("BEACON", "");
                nextBeacon = now + BeaconInterval;
            }
            if (now >= nextAddressRefresh)
            {
                RefreshLocalAddresses();
                nextAddressRefresh = now + LocalAddressesRefresh;
            }
            RemoveExpiredPeers(now);
        }

        Send("BYE", "");
        WriteLog("Завершение работы");
        _log.Dispose();
        _socket.Dispose();
        Print("Вы вышли из чата.");
        return 0;
    }

    static Socket CreateSocket()
    {
        var socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
        socket.EnableBroadcast = true; // SO_BROADCAST
        socket.Blocking = false;       // неблокирующий режим

        if (OperatingSystem.IsWindows())
        {
            // SIO_UDP_CONNRESET: иначе Windows после ICMP "port unreachable"
            // бросает ConnectionReset на следующем ReceiveFrom.
            const int SioUdpConnReset = -1744830452;
            socket.IOControl(SioUdpConnReset, new byte[] { 0, 0, 0, 0 }, null);
        }

        socket.Bind(new IPEndPoint(IPAddress.Any, Port));
        return socket;
    }

    //Приём 

    static void ReceiveAll()
    {
        byte[] buffer = new byte[65535];

        // Читаем все накопившиеся датаграммы, пока сокет не скажет WouldBlock.
        for (;;)
        {
            EndPoint remote = new IPEndPoint(IPAddress.Any, 0);
            int received;
            try
            {
                received = _socket.ReceiveFrom(buffer, ref remote);
            }
            catch (SocketException ex) when (ex.SocketErrorCode == SocketError.WouldBlock)
            {
                return;
            }
            catch (SocketException ex) when (ex.SocketErrorCode is SocketError.ConnectionReset or SocketError.MessageSize)
            {
                continue;
            }

            var sender = (IPEndPoint)remote;
            HandleDatagram(sender, buffer.AsSpan(0, received));
        }
    }

    static void HandleDatagram(IPEndPoint sender, ReadOnlySpan<byte> data)
    {
        string text;
        try
        {
            text = StrictUtf8.GetString(data);
        }
        catch (DecoderFallbackException)
        {
            WriteLog($"ПОЛУЧЕНО от {sender}, {data.Length} байт, не UTF-8 (игнор): {Convert.ToHexString(data)}");
            return;
        }

        IPAddress ip = Normalize(sender.Address);
        bool own = _localAddresses.Contains(ip);
        WriteLog($"ПОЛУЧЕНО от {sender}, {data.Length} байт{(own ? " (свой пакет, игнор)" : "")}: {text}");
        if (own)
            return;

        if (!TryParse(text, out string type, out string name, out string body))
        {
            WriteLog($"Некорректный пакет от {sender} проигнорирован");
            return;
        }

        switch (type)
        {
            case "DISCOVER":
                TouchPeer(ip, name);
                Send("BEACON", "");
                break;
            case "BEACON":
                TouchPeer(ip, name);
                break;
            case "MSG":
                TouchPeer(ip, name);
                Print($"{name}: {body}");
                break;
            case "BYE":
                if (Peers.Remove(ip, out Peer? peer))
                    Print($"* {peer.Name} ({ip}) покинул(а) чат");
                break;
        }
    }

    // Формат: ТИП|Имя|Текст. Делим максимум на 3 части, текст может содержать '|'.
    static bool TryParse(string packet, out string type, out string name, out string body)
    {
        type = name = body = "";
        packet = packet.TrimEnd('\r', '\n', '\0');

        string[] parts = packet.Split('|', 3);
        if (parts.Length < 2)
            return false;

        type = parts[0];
        if (type is not ("DISCOVER" or "BEACON" or "BYE" or "MSG"))
            return false;

        name = Sanitize(parts[1]).Trim();
        if (name.Length == 0)
            return false;

        body = parts.Length == 3 ? Sanitize(parts[2]) : "";
        return true;
    }

    //Таблица узлов 

    static void TouchPeer(IPAddress ip, string name)
    {
        if (Peers.TryGetValue(ip, out Peer? peer))
        {
            if (peer.Name != name)
                Print($"* {peer.Name} ({ip}) теперь {name}");
            peer.Name = name;
            peer.LastSeen = DateTime.Now;
        }
        else
        {
            Peers[ip] = new Peer { Name = name, LastSeen = DateTime.Now };
            Print($"* {name} ({ip}) в сети");
        }
    }

    static void RemoveExpiredPeers(DateTime now)
    {
        foreach (var (ip, peer) in Peers.Where(p => now - p.Value.LastSeen > PeerTimeout).ToList())
        {
            Peers.Remove(ip);
            Print($"* {peer.Name} ({ip}) пропал(а) - нет сообщений {PeerTimeout.TotalSeconds:0} с");
        }
    }

    static void PrintPeers()
    {
        if (Peers.Count == 0)
        {
            Print("Активных узлов нет.");
            return;
        }
        var sb = new StringBuilder($"Активные узлы ({Peers.Count}):");
        foreach (var (ip, peer) in Peers.OrderBy(p => p.Value.Name))
            sb.Append($"\n  {peer.Name,-20} {ip,-15} последнее сообщение: {peer.LastSeen:HH:mm:ss}");
        Print(sb.ToString());
    }

    // Отправка 

    static void Send(string type, string body)
    {
        string header = $"{type}|{_myName}|";
        int budget = MaxPacketBytes - Encoding.UTF8.GetByteCount(header);
        string packet = header + TruncateUtf8(body, budget);
        byte[] data = Encoding.UTF8.GetBytes(packet);
        var target = new IPEndPoint(BroadcastAddress, Port);

        try
        {
            int sent = _socket.SendTo(data, target);
            WriteLog($"ОТПРАВЛЕНО на {target}, {sent} байт: {packet}");
        }
        catch (SocketException ex)
        {
            // В неблокирующем режиме буфер может быть занят (WouldBlock), или сети нет вовсе.
            WriteLog($"ОШИБКА отправки на {target} ({ex.SocketErrorCode}): {packet}");
            Print($"! Не удалось отправить {type}: {ex.SocketErrorCode}");
        }
    }

    // Обрезает строку так, чтобы её UTF-8 представление влезло в maxBytes, не разрезая символы.
    static string TruncateUtf8(string s, int maxBytes)
    {
        if (Encoding.UTF8.GetByteCount(s) <= maxBytes)
            return s;
        var sb = new StringBuilder();
        int bytes = 0;
        foreach (Rune r in s.EnumerateRunes())
        {
            if (bytes + r.Utf8SequenceLength > maxBytes)
                break;
            bytes += r.Utf8SequenceLength;
            sb.Append(r.ToString());
        }
        return sb.ToString();
    }

    // ---------- Консоль ----------

    static void StartInputThread()
    {
        // Консольный ввод читается в отдельном потоке, а все операции с сокетом -
        // в главном цикле, поэтому ReadLine не мешает приёму пакетов.
        var thread = new Thread(() =>
        {
            while (_running)
            {
                string? line = Console.ReadLine();
                if (line == null)
                {
                    _running = false; // конец ввода (Ctrl+D / Ctrl+Z)
                    return;
                }
                InputLines.Enqueue(line);
            }
        }) { IsBackground = true };
        thread.Start();
    }

    static void HandleInput(string line)
    {
        string trimmed = line.Trim();
        if (trimmed.Length == 0)
            return;

        switch (trimmed)
        {
            case "/quit":
            case "/exit":
                _running = false;
                return;
            case "/list":
                PrintPeers();
                return;
        }

        Send("MSG", Sanitize(line));
    }

    static void Print(string message)
    {
        lock (ConsoleLock)
            Console.WriteLine(message);
    }

    // Вспомогательное 

    static bool IsValidName(string name) =>
        name.Length is >= 1 and <= MaxNameLength && !name.Contains('|') && !name.Contains('\n') && !name.Contains('\r');

    // Переводы строки и прочие управляющие символы заменяем пробелом.
    static string Sanitize(string s) =>
        string.Create(s.Length, s, (span, src) =>
        {
            for (int i = 0; i < src.Length; i++)
                span[i] = char.IsControl(src[i]) ? ' ' : src[i];
        });

    static IPAddress Normalize(IPAddress ip) => ip.IsIPv4MappedToIPv6 ? ip.MapToIPv4() : ip;

    // Свои пакеты отсеиваем по локальным IP (broadcast возвращается отправителю).
    // Список обновляется периодически: адрес может смениться при переподключении к Wi-Fi.
    static void RefreshLocalAddresses()
    {
        var set = new HashSet<IPAddress> { IPAddress.Loopback };
        try
        {
            foreach (NetworkInterface ni in NetworkInterface.GetAllNetworkInterfaces())
                foreach (UnicastIPAddressInformation addr in ni.GetIPProperties().UnicastAddresses)
                    if (addr.Address.AddressFamily == AddressFamily.InterNetwork)
                        set.Add(addr.Address);
        }
        catch (NetworkInformationException)
        {
            // оставляем хотя бы loopback
        }
        _localAddresses = set;
    }

    static void WriteLog(string line)
    {
        _log.WriteLine($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] {Sanitize(line)}");
    }
}
