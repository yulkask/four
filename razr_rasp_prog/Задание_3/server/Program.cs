using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text;

namespace ChatServer;

// Состояние одного подключения.
sealed class Client
{
    public required Socket Socket;
    public required string Address;
    public string? Nick;                         // null, пока клиент не прислал корректный ник
    public readonly List<byte> InBuffer = new(); // принятые байты, ещё не разобранные на строки
    public bool SkipUntilNewline;                // хвост слишком длинной строки отбрасывается
    public readonly Queue<byte[]> OutQueue = new();
    public int OutOffset;                        // сколько байтов первого элемента очереди уже отправлено
    public int OutBytes;                         // всего байтов в очереди
    public bool CloseAfterFlush;                 // дописать очередь и закрыть (после *** error)
    public bool Dead;                            // удалить в конце итерации

    public string Name => Nick ?? Address;
}

static class Program
{
    // Константы протокола, общие для всей аудитории.
    const int DefaultPort = 50001;
    const int MaxLineBytes = 1024;
    const int MaxNickLength = 20;

    // Если клиент не читает данные и у него накопилось столько байтов, отключаем его,
    // чтобы не расходовать память сервера.
    const int MaxOutBytes = 1024 * 1024;

    // Строгий декодер: на некорректном UTF-8 бросает исключение, и строка игнорируется.
    static readonly UTF8Encoding StrictUtf8 = new(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true);

    static readonly List<Client> Clients = new();
    static readonly object ConsoleLock = new();
    static volatile bool _running = true;

    static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;

        int port = DefaultPort;
        if (args.Length > 0 && (!int.TryParse(args[0], out port) || port is < 1 or > 65535))
        {
            Console.Error.WriteLine("Использование: dotnet run -- [порт]");
            return 1;
        }

        Socket listener = new(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
        try
        {
            listener.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
            listener.Bind(new IPEndPoint(IPAddress.Any, port));
            listener.Listen(16);
        }
        catch (SocketException e)
        {
            Console.Error.WriteLine($"Не удалось открыть порт {port}: {e.Message}");
            return 1;
        }
        listener.Blocking = false;

        Console.CancelKeyPress += (_, e) =>
        {
            e.Cancel = true;
            _running = false;
        };

        Log($"Сервер запущен на TCP-порту {port}. Остановка: Ctrl+C.");
        foreach (string ip in LocalIPv4Addresses())
            Log($"Адрес для клиентов: {ip}");

        try
        {
            RunLoop(listener);
        }
        finally
        {
            Shutdown(listener);
        }
        return 0;
    }

    // Главный цикл: один поток, Select по всем сокетам. Ни один вызов не блокируется
    // на конкретном клиенте, поэтому зависший клиент не мешает остальным.
    static void RunLoop(Socket listener)
    {
        byte[] buffer = new byte[4096];

        while (_running)
        {
            List<Socket> readList = new() { listener };
            List<Socket> writeList = new();
            List<Socket> errorList = new();
            foreach (Client c in Clients)
            {
                if (!c.CloseAfterFlush)
                    readList.Add(c.Socket);
                if (c.OutBytes > 0)
                    writeList.Add(c.Socket);
                errorList.Add(c.Socket);
            }

            // Таймаут 200 мс, чтобы регулярно проверять флаг остановки (Ctrl+C).
            try
            {
                Socket.Select(readList, writeList.Count > 0 ? writeList : null, errorList, 200_000);
            }
            catch (SocketException e) when (e.SocketErrorCode == SocketError.Interrupted)
            {
                continue; // Select прерван сигналом (например, Ctrl+C) - проверяем флаг и повторяем
            }

            if (readList.Remove(listener))
                AcceptAll(listener);

            foreach (Socket s in errorList)
            {
                Client? c = Find(s);
                if (c != null)
                    Drop(c, "ошибка сокета");
            }

            foreach (Socket s in readList)
            {
                Client? c = Find(s);
                if (c != null && !c.Dead)
                    ReadFrom(c, buffer);
            }

            foreach (Socket s in writeList)
            {
                Client? c = Find(s);
                if (c != null && !c.Dead)
                    Flush(c);
            }

            RemoveDead();
        }
    }

    static Client? Find(Socket s)
    {
        foreach (Client c in Clients)
            if (c.Socket == s)
                return c;
        return null;
    }

    static void AcceptAll(Socket listener)
    {
        while (true)
        {
            Socket socket;
            try
            {
                socket = listener.Accept();
            }
            catch (SocketException)
            {
                return; // очередь входящих подключений пуста
            }

            socket.Blocking = false;
            socket.NoDelay = true;
            string address = socket.RemoteEndPoint?.ToString() ?? "?";
            Clients.Add(new Client { Socket = socket, Address = address });
            Log($"Подключение от {address}, ждём ник");
        }
    }

    static void ReadFrom(Client c, byte[] buffer)
    {
        int n = c.Socket.Receive(buffer, 0, buffer.Length, SocketFlags.None, out SocketError error);
        if (error == SocketError.WouldBlock)
            return;
        if (error != SocketError.Success)
        {
            Drop(c, $"обрыв соединения ({error})");
            return;
        }
        if (n == 0)
        {
            Drop(c, "соединение закрыто клиентом");
            return;
        }

        for (int i = 0; i < n && !c.Dead && !c.CloseAfterFlush; i++)
        {
            byte b = buffer[i];
            if (b == (byte)'\n')
            {
                if (c.SkipUntilNewline)
                    c.SkipUntilNewline = false;
                else
                    CompleteLine(c);
                continue;
            }
            if (c.SkipUntilNewline)
                continue;

            c.InBuffer.Add(b);
            if (c.InBuffer.Count > MaxLineBytes)
            {
                // Слишком длинная строка: оставляем первые 1024 байта, остальное до \n отбрасываем.
                c.InBuffer.RemoveRange(MaxLineBytes, c.InBuffer.Count - MaxLineBytes);
                Log($"{c.Name}: строка длиннее {MaxLineBytes} байт, обрезана");
                CompleteLine(c);
                c.SkipUntilNewline = true;
            }
        }
    }

    static void CompleteLine(Client c)
    {
        byte[] bytes = c.InBuffer.ToArray();
        c.InBuffer.Clear();

        int length = bytes.Length;
        if (length > 0 && bytes[length - 1] == (byte)'\r')
            length--;

        string line;
        try
        {
            line = StrictUtf8.GetString(bytes, 0, length);
        }
        catch (DecoderFallbackException)
        {
            // Обрезка могла разрезать многобайтовый символ: убираем неполный хвост и пробуем снова.
            int cut = Utf8CutPoint(bytes, length);
            try
            {
                line = StrictUtf8.GetString(bytes, 0, cut);
            }
            catch (DecoderFallbackException)
            {
                Log($"{c.Name}: строка не в UTF-8, пропущена");
                return;
            }
        }

        if (line.Length == 0)
            return;

        if (c.Nick == null)
            Register(c, line);
        else
            HandleLine(c, line);
    }

    static void Register(Client c, string nick)
    {
        string? problem = ValidateNick(nick, c);
        if (problem != null)
        {
            Log($"{c.Address}: ник \"{nick}\" отклонён: {problem}");
            Send(c, $"*** error: {problem}");
            c.CloseAfterFlush = true;
            return;
        }

        c.Nick = nick;
        Log($"{c.Address} вошёл(ла) как {nick}");
        BroadcastExcept(c, $"*** {nick} joined");
    }

    static void HandleLine(Client c, string line)
    {
        if (!line.StartsWith('/'))
        {
            SendChat(c, line);
            return;
        }

        int space = line.IndexOf(' ');
        string command = space < 0 ? line : line[..space];
        string argument = space < 0 ? "" : line[(space + 1)..];

        switch (command)
        {
            case "/msg":
                if (argument.Length > 0)
                    SendChat(c, argument);
                break;

            case "/list":
                List<string> nicks = Clients.Where(x => x.Nick != null && !x.Dead).Select(x => x.Nick!).ToList();
                Send(c, $"*** online ({nicks.Count}): {string.Join(", ", nicks)}");
                Log($"{c.Nick} запросил(а) список");
                break;

            case "/nick":
                ChangeNick(c, argument);
                break;

            case "/quit":
                Drop(c, "команда /quit");
                break;

            default:
                Send(c, "*** error: unknown command");
                Log($"{c.Nick}: неизвестная команда {command}");
                break;
        }
    }

    static void SendChat(Client c, string text)
    {
        Log($"[{c.Nick}]: {text}");
        BroadcastExcept(c, $"[{c.Nick}]: {text}");
    }

    static void ChangeNick(Client c, string newNick)
    {
        string? problem = ValidateNick(newNick, c);
        if (problem == null && newNick == c.Nick)
            problem = "this is already your nick";
        if (problem != null)
        {
            Send(c, $"*** error: {problem}");
            Log($"{c.Nick}: смена ника на \"{newNick}\" отклонена: {problem}");
            return;
        }

        string oldNick = c.Nick!;
        c.Nick = newNick;
        Log($"{oldNick} сменил(а) ник на {newNick}");
        BroadcastAll($"*** {oldNick} is now known as {newNick}");
    }

    // Возвращает причину отказа или null, если ник подходит.
    // self - клиент, который регистрирует или меняет ник: его текущий ник не считается занятым.
    static string? ValidateNick(string nick, Client self)
    {
        if (nick.Length == 0)
            return "nick is empty";
        int length = 0;
        foreach (Rune r in nick.EnumerateRunes())
        {
            if (Rune.IsWhiteSpace(r))
                return "nick must not contain spaces";
            if (Rune.IsControl(r))
                return "nick must not contain control characters";
            length++;
        }
        if (length > MaxNickLength)
            return $"nick must be 1-{MaxNickLength} characters";

        foreach (Client other in Clients)
        {
            if (other != self && !other.Dead && other.Nick != null &&
                string.Equals(other.Nick, nick, StringComparison.OrdinalIgnoreCase))
                return "nick is already taken";
        }
        return null;
    }

    static void BroadcastExcept(Client sender, string line)
    {
        foreach (Client c in Clients.ToList())
            if (c != sender && c.Nick != null && !c.Dead)
                Send(c, line);
    }

    static void BroadcastAll(string line)
    {
        foreach (Client c in Clients.ToList())
            if (c.Nick != null && !c.Dead)
                Send(c, line);
    }

    // Ставит строку в очередь клиента и сразу пытается отправить. Остаток уйдёт,
    // когда Select сообщит, что сокет готов к записи.
    static void Send(Client c, string line)
    {
        byte[] data = Encoding.UTF8.GetBytes(TruncateUtf8(line, MaxLineBytes) + "\n");
        c.OutQueue.Enqueue(data);
        c.OutBytes += data.Length;
        if (c.OutBytes > MaxOutBytes)
        {
            Drop(c, "клиент не читает данные, очередь переполнена");
            return;
        }
        Flush(c);
    }

    static void Flush(Client c)
    {
        while (c.OutQueue.Count > 0)
        {
            byte[] data = c.OutQueue.Peek();
            int sent = c.Socket.Send(data, c.OutOffset, data.Length - c.OutOffset, SocketFlags.None, out SocketError error);
            if (error == SocketError.WouldBlock)
                return;
            if (error != SocketError.Success)
            {
                Drop(c, $"ошибка отправки ({error})");
                return;
            }
            c.OutOffset += sent;
            c.OutBytes -= sent;
            if (c.OutOffset < data.Length)
                return;
            c.OutQueue.Dequeue();
            c.OutOffset = 0;
        }

        if (c.CloseAfterFlush)
            Drop(c, "соединение закрыто сервером");
    }

    // Помечает клиента отключённым и сообщает остальным. Сам сокет закрывается в RemoveDead.
    static void Drop(Client c, string reason)
    {
        if (c.Dead)
            return;
        c.Dead = true;
        Log($"{c.Name} отключился(лась): {reason}");
        if (c.Nick != null)
            BroadcastExcept(c, $"*** {c.Nick} left");
    }

    static void RemoveDead()
    {
        foreach (Client c in Clients.Where(x => x.Dead).ToList())
        {
            CloseSocket(c.Socket);
            Clients.Remove(c);
        }
    }

    static void Shutdown(Socket listener)
    {
        Log("Сервер останавливается");
        foreach (Client c in Clients)
        {
            try
            {
                c.Socket.Blocking = true;
                c.Socket.SendTimeout = 500;
                c.Socket.Send(Encoding.UTF8.GetBytes("*** server is shutting down\n"));
            }
            catch (SocketException) { }
            CloseSocket(c.Socket);
        }
        Clients.Clear();
        listener.Close();
    }

    static void CloseSocket(Socket s)
    {
        try
        {
            s.Shutdown(SocketShutdown.Both);
        }
        catch (SocketException) { }
        catch (ObjectDisposedException) { }
        s.Close();
    }

    static string TruncateUtf8(string s, int maxBytes)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(s);
        if (bytes.Length <= maxBytes)
            return s;
        return Encoding.UTF8.GetString(bytes, 0, Utf8CutPoint(bytes, maxBytes));
    }

    // Наибольшая длина <= limit, на которой не обрывается многобайтовый символ UTF-8.
    static int Utf8CutPoint(byte[] bytes, int limit)
    {
        if (limit == 0)
            return 0;
        int start = limit - 1; // начало последнего символа перед границей
        while (start > 0 && (bytes[start] & 0xC0) == 0x80)
            start--;
        int charLength = bytes[start] switch
        {
            >= 0xF0 => 4,
            >= 0xE0 => 3,
            >= 0xC0 => 2,
            _ => 1,
        };
        return start + charLength <= limit ? limit : start;
    }

    static IEnumerable<string> LocalIPv4Addresses()
    {
        foreach (NetworkInterface ni in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (ni.OperationalStatus != OperationalStatus.Up || ni.NetworkInterfaceType == NetworkInterfaceType.Loopback)
                continue;
            foreach (UnicastIPAddressInformation a in ni.GetIPProperties().UnicastAddresses)
                if (a.Address.AddressFamily == AddressFamily.InterNetwork)
                    yield return $"{a.Address} ({ni.Name})";
        }
    }

    static void Log(string message)
    {
        lock (ConsoleLock)
            Console.WriteLine($"{DateTime.Now:HH:mm:ss} {message}");
    }
}
