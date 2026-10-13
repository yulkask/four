using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text;

namespace SmtpServer;

// Состояние одной SMTP-сессии.
sealed class Session
{
    public bool Greeted;                         // клиент прислал EHLO/HELO
    public string? From;                         // null, пока не было MAIL FROM
    public readonly List<string> To = new();

    // Сброс конверта: после доставленного письма, по RSET и по повторному EHLO.
    public void Reset()
    {
        From = null;
        To.Clear();
    }
}

static class Program
{
    const int DefaultPort = 2525;

    // Защита от клиентов, которые присылают бесконечные строки или письма.
    const int MaxLineChars = 1000;               // RFC 5321, 4.5.3.1.6
    const int MaxMessageChars = 10 * 1024 * 1024;
    static readonly TimeSpan IdleTimeout = TimeSpan.FromMinutes(5);

    static readonly object ConsoleLock = new();
    static int _nextClientId;

    static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;

        int port = DefaultPort;
        bool lan = false;
        foreach (string arg in args)
        {
            if (arg == "--lan")
                lan = true;
            else if (!int.TryParse(arg, out port) || port is < 1 or > 65535)
            {
                Console.Error.WriteLine("Использование: dotnet run -- [порт] [--lan]");
                return 1;
            }
        }

        // По заданию сервер слушает только localhost. С --lan он доступен и с других компьютеров сети.
        TcpListener listener = new(lan ? IPAddress.Any : IPAddress.Loopback, port);
        try
        {
            listener.Start();
        }
        catch (SocketException e)
        {
            Console.Error.WriteLine($"Не удалось открыть порт {port}: {e.Message}");
            return 1;
        }

        Console.CancelKeyPress += (_, e) =>
        {
            e.Cancel = true;
            listener.Stop(); // AcceptTcpClient бросит исключение, и цикл завершится
        };

        Log(0, $"SMTP-сервер слушает {(lan ? "все интерфейсы" : "localhost")}:{port}. Остановка: Ctrl+C.");
        if (lan)
            foreach (string ip in LocalIPv4Addresses())
                Log(0, $"Адрес для клиентов: {ip}");

        while (true)
        {
            TcpClient tcp;
            try
            {
                tcp = listener.AcceptTcpClient();
            }
            catch (SocketException)
            {
                break;
            }
            catch (ObjectDisposedException)
            {
                break;
            }

            // Каждый клиент обслуживается в своём потоке, чтобы медленный клиент не задерживал остальных.
            int id = Interlocked.Increment(ref _nextClientId);
            new Thread(() => Serve(tcp, id)) { IsBackground = true }.Start();
        }

        Log(0, "Сервер остановлен.");
        return 0;
    }

    static void Serve(TcpClient tcp, int id)
    {
        Log(id, $"Подключился {tcp.Client.RemoteEndPoint}");
        try
        {
            using (tcp)
            {
                tcp.ReceiveTimeout = (int)IdleTimeout.TotalMilliseconds;
                using NetworkStream stream = tcp.GetStream();
                using StreamReader reader = new(stream, new UTF8Encoding(false));
                using StreamWriter writer = new(stream, new UTF8Encoding(false)) { NewLine = "\r\n", AutoFlush = true };

                RunSession(id, reader, writer);
            }
        }
        catch (IOException e)
        {
            Log(id, $"Соединение прервано: {e.Message}");
        }
        catch (LineTooLongException)
        {
            Log(id, "Слишком длинная строка, соединение закрыто.");
        }
        Log(id, "Отключился");
    }

    static void RunSession(int id, StreamReader reader, StreamWriter writer)
    {
        Session s = new();
        Reply(id, writer, "220 localhost SMTP Test Server");

        while (true)
        {
            string? line = ReadLine(reader);
            if (line == null)
                return; // клиент закрыл соединение без QUIT
            Log(id, $"C: {line}");

            // Команда - первые 4 символа без учёта регистра; аргумент - всё, что после них.
            string verb = line.Length >= 4 ? line[..4].ToUpperInvariant() : line.ToUpperInvariant();
            string arg = line.Length > 4 ? line[4..].Trim() : "";

            switch (verb)
            {
                case "EHLO":
                case "HELO":
                    s.Greeted = true;
                    s.Reset();
                    Reply(id, writer, verb == "EHLO" ? "250-Hello\r\n250 HELP" : "250 Hello");
                    break;

                case "MAIL":
                    if (!s.Greeted)
                        Reply(id, writer, "503 Send EHLO first");
                    else if (s.From != null)
                        Reply(id, writer, "503 Sender already specified");
                    else if (ParsePath(arg, "FROM:") is not { } from)
                        Reply(id, writer, "501 Syntax: MAIL FROM:<address>");
                    else
                    {
                        s.From = from;
                        Reply(id, writer, "250 OK");
                    }
                    break;

                case "RCPT":
                    if (s.From == null)
                        Reply(id, writer, "503 Need MAIL FROM first");
                    else if (ParsePath(arg, "TO:") is not { Length: > 0 } to)
                        Reply(id, writer, "501 Syntax: RCPT TO:<address>");
                    else
                    {
                        s.To.Add(to);
                        Reply(id, writer, "250 OK");
                    }
                    break;

                case "DATA":
                    if (s.To.Count == 0)
                    {
                        Reply(id, writer, "503 Need RCPT TO first");
                        break;
                    }
                    Reply(id, writer, "354 End data with <CR><LF>.<CR><LF>");
                    string? body = ReadData(reader);
                    if (body == null)
                        return; // соединение оборвалось посреди письма - письмо не принято
                    if (body.Length > MaxMessageChars)
                        Reply(id, writer, "552 Message too large");
                    else
                    {
                        LogMessage(id, s, body);
                        Reply(id, writer, "250 OK: message accepted");
                    }
                    s.Reset();
                    break;

                case "RSET":
                    s.Reset();
                    Reply(id, writer, "250 OK");
                    break;

                case "NOOP":
                    Reply(id, writer, "250 OK");
                    break;

                case "QUIT":
                    Reply(id, writer, "221 Bye");
                    return;

                default:
                    Reply(id, writer, "500 Command not recognized");
                    break;
            }
        }
    }

    // Читает тело письма до строки из одной точки. Возвращает null, если соединение оборвалось.
    // Слишком большое письмо дочитывается до конца, но не сохраняется.
    static string? ReadData(StreamReader reader)
    {
        StringBuilder body = new();
        while (true)
        {
            string? line = ReadLine(reader);
            if (line == null)
                return null;
            if (line == ".")
                return body.ToString();
            // Обратный dot-stuffing: клиент удваивает точку в начале строки.
            if (line.StartsWith('.'))
                line = line[1..];
            if (body.Length <= MaxMessageChars)
                body.Append(line).Append("\r\n");
        }
    }

    // Извлекает адрес из "FROM:<a@b>" / "TO:<a@b>". Пустой адрес "<>" допустим для MAIL FROM.
    // Параметры расширений после адреса (например, "SIZE=100") игнорируются.
    static string? ParsePath(string arg, string prefix)
    {
        if (!arg.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            return null;
        string rest = arg[prefix.Length..].TrimStart();
        if (rest.StartsWith('<'))
        {
            int end = rest.IndexOf('>');
            return end < 0 ? null : rest[1..end];
        }
        // Некоторые клиенты отправляют адрес без угловых скобок.
        string addr = rest.Split(' ', 2)[0];
        return addr.Length > 0 ? addr : null;
    }

    // ReadLine без ограничения длины позволил бы клиенту занять всю память сервера.
    static string? ReadLine(StreamReader reader)
    {
        StringBuilder sb = new();
        while (true)
        {
            int c = reader.Read();
            if (c == -1)
                return sb.Length > 0 ? sb.ToString() : null;
            if (c == '\n')
                break;
            if (sb.Length >= MaxLineChars)
                throw new LineTooLongException();
            sb.Append((char)c);
        }
        if (sb.Length > 0 && sb[^1] == '\r')
            sb.Length--;
        return sb.ToString();
    }

    static void Reply(int id, StreamWriter writer, string reply)
    {
        foreach (string line in reply.Split("\r\n"))
            Log(id, $"S: {line}");
        writer.WriteLine(reply);
    }

    static void LogMessage(int id, Session s, string body)
    {
        lock (ConsoleLock)
        {
            Console.WriteLine();
            Console.WriteLine($"========== Письмо (клиент #{id}) ==========");
            Console.WriteLine($"Отправитель: {(s.From is "" ? "<>" : s.From)}");
            Console.WriteLine($"Получатели:  {string.Join(", ", s.To)}");
            Console.WriteLine("---------- Тело письма ----------");
            Console.Write(body.Replace("\r\n", Environment.NewLine));
            Console.WriteLine("=================================");
            Console.WriteLine();
        }
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

    static void Log(int id, string text)
    {
        lock (ConsoleLock)
            Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] {(id > 0 ? $"#{id} " : "")}{text}");
    }
}

sealed class LineTooLongException : Exception;
