using System.Globalization;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;

namespace SmtpClientApp;

// Ошибка SMTP-диалога: сервер ответил не тем кодом, которого ждали.
sealed class SmtpException(string message) : Exception(message);

// Параметры запуска. Значения по умолчанию взяты из условия задания 2.
sealed class Options
{
    public string Host = "localhost";
    public int Port = 25;
    public string From = "test@localhost";
    public string To = "user@localhost";
    public string Subject = "Test from SMTP Client";
    public string Text = "Hello! This message was sent by my own SMTP client.";
    public string? User;     // логин для AUTH; без него аутентификация не выполняется
    public string? Password;
}

static class Program
{
    static readonly TimeSpan Timeout = TimeSpan.FromSeconds(30);

    static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;

        Options? opt = ParseArgs(args);
        if (opt == null)
        {
            PrintUsage();
            return 1;
        }

        try
        {
            Send(opt);
            Console.WriteLine("Письмо успешно отправлено.");
            return 0;
        }
        catch (SmtpException e)
        {
            Console.Error.WriteLine($"Ошибка SMTP: {e.Message}");
        }
        catch (SocketException e)
        {
            Console.Error.WriteLine($"Не удалось подключиться к {opt.Host}:{opt.Port}: {e.Message}");
        }
        catch (IOException e)
        {
            Console.Error.WriteLine($"Соединение прервано: {e.Message}");
        }
        return 1;
    }

    static void Send(Options opt)
    {
        // 1. Установка соединения.
        using TcpClient tcp = new();
        tcp.ReceiveTimeout = tcp.SendTimeout = (int)Timeout.TotalMilliseconds;
        tcp.Connect(opt.Host, opt.Port);
        Console.WriteLine($"Подключено к {opt.Host}:{opt.Port}");

        using NetworkStream stream = tcp.GetStream();
        // SMTP - текстовый протокол со строками, оканчивающимися на CRLF.
        using StreamReader reader = new(stream, new UTF8Encoding(false));
        using StreamWriter writer = new(stream, new UTF8Encoding(false)) { NewLine = "\r\n", AutoFlush = true };

        Expect(reader, 220);

        // 2. Начало сессии. Ответ на EHLO многострочный: в нём перечислены расширения сервера.
        List<string> ehlo = Command(reader, writer, "EHLO localhost", 250);

        if (opt.User != null)
            Authenticate(reader, writer, ehlo, opt.User, opt.Password ?? "");

        // 3. Конверт письма.
        Command(reader, writer, $"MAIL FROM:<{opt.From}>", 250);
        SendLine(writer, $"RCPT TO:<{opt.To}>");
        Expect(reader, 250, 251); // 251 - "пользователь не местный, письмо будет переслано"
        Command(reader, writer, "DATA", 354);

        // Тело письма: заголовки, пустая строка, текст, завершающая точка.
        string[] headers =
        [
            $"From: Test User <{opt.From}>",
            $"To: Recipient <{opt.To}>",
            $"Subject: {opt.Subject}",
            $"Date: {RfcDate(DateTimeOffset.Now)}",
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=utf-8",
            "Content-Transfer-Encoding: 8bit",
        ];
        foreach (string h in headers)
            SendLine(writer, h);
        SendLine(writer, "");
        foreach (string line in opt.Text.Replace("\r\n", "\n").Split('\n'))
        {
            // Dot-stuffing (RFC 5321, 4.5.2): строку, начинающуюся с точки, дополняем ещё одной,
            // иначе сервер может принять её за конец письма.
            SendLine(writer, line.StartsWith('.') ? "." + line : line);
        }
        // Вместе с CRLF предыдущей строки получается последовательность \r\n.\r\n
        SendLine(writer, ".");
        Expect(reader, 250);

        // 4. Завершение.
        Command(reader, writer, "QUIT", 221);
    }

    // Выбирает самый надёжный из поддерживаемых сервером методов аутентификации.
    static void Authenticate(StreamReader reader, StreamWriter writer, List<string> ehlo, string user, string password)
    {
        HashSet<string> methods = new(StringComparer.OrdinalIgnoreCase);
        foreach (string line in ehlo)
        {
            // Строка вида "AUTH LOGIN PLAIN CRAM-MD5" (или устаревшая "AUTH=LOGIN").
            string ext = line.Length > 4 ? line[4..] : "";
            if (ext.StartsWith("AUTH", StringComparison.OrdinalIgnoreCase) && ext.Length > 4 && ext[4] is ' ' or '=')
                methods.UnionWith(ext[5..].Split(' ', StringSplitOptions.RemoveEmptyEntries));
        }

        if (methods.Contains("CRAM-MD5"))
        {
            // Сервер присылает случайную строку, клиент отвечает "user HMAC-MD5(пароль, строка)".
            // Пароль по сети не передаётся.
            string challenge = Encoding.UTF8.GetString(Convert.FromBase64String(Command(reader, writer, "AUTH CRAM-MD5", 334)[^1][4..]));
            byte[] hash = HMACMD5.HashData(Encoding.UTF8.GetBytes(password), Encoding.UTF8.GetBytes(challenge));
            string response = $"{user} {Convert.ToHexString(hash).ToLowerInvariant()}";
            Command(reader, writer, Base64(response), 235, secret: true);
        }
        else if (methods.Contains("LOGIN"))
        {
            Command(reader, writer, "AUTH LOGIN", 334);
            Command(reader, writer, Base64(user), 334);
            Command(reader, writer, Base64(password), 235, secret: true);
        }
        else if (methods.Contains("PLAIN"))
        {
            Command(reader, writer, "AUTH PLAIN " + Base64($"\0{user}\0{password}"), 235, secret: true);
        }
        else
        {
            throw new SmtpException("сервер не поддерживает AUTH CRAM-MD5, LOGIN или PLAIN");
        }
    }

    static string Base64(string s) => Convert.ToBase64String(Encoding.UTF8.GetBytes(s));

    // Дата в формате RFC 5322: "Tue, 13 Oct 2026 12:30:00 +0300".
    static string RfcDate(DateTimeOffset d)
    {
        string offset = d.ToString("zzz", CultureInfo.InvariantCulture).Replace(":", "");
        return d.ToString("ddd, dd MMM yyyy HH:mm:ss ", CultureInfo.InvariantCulture) + offset;
    }

    // Отправляет команду и проверяет код ответа. Возвращает все строки ответа.
    static List<string> Command(StreamReader reader, StreamWriter writer, string command, int expected, bool secret = false)
    {
        SendLine(writer, command, secret);
        return Expect(reader, expected);
    }

    static void SendLine(StreamWriter writer, string line, bool secret = false)
    {
        Console.WriteLine($"C: {(secret ? "********" : line)}");
        writer.WriteLine(line);
    }

    // Читает ответ сервера. Многострочный ответ имеет вид "250-...", "250-...", "250 ..." -
    // последняя строка отличается пробелом после кода.
    static List<string> Expect(StreamReader reader, params int[] expected)
    {
        List<string> lines = new();
        while (true)
        {
            string line = reader.ReadLine() ?? throw new IOException("сервер закрыл соединение");
            Console.WriteLine($"S: {line}");
            if (line.Length < 3 || !int.TryParse(line.AsSpan(0, 3), out _))
                throw new SmtpException($"некорректный ответ сервера: {line}");
            lines.Add(line);
            if (line.Length == 3 || line[3] != '-')
                break;
        }

        int code = int.Parse(lines[^1].AsSpan(0, 3));
        if (!expected.Contains(code))
            throw new SmtpException($"ожидался код {string.Join(" или ", expected)}, получен: {lines[^1]}");
        return lines;
    }

    static Options? ParseArgs(string[] args)
    {
        Options opt = new();
        for (int i = 0; i < args.Length; i++)
        {
            if (i + 1 >= args.Length)
                return null;
            string value = args[++i];
            switch (args[i - 1])
            {
                case "--host": opt.Host = value; break;
                case "--port":
                    if (!int.TryParse(value, out opt.Port) || opt.Port is < 1 or > 65535)
                        return null;
                    break;
                case "--from": opt.From = value; break;
                case "--to": opt.To = value; break;
                case "--subject": opt.Subject = value; break;
                case "--text": opt.Text = value; break;
                case "--user": opt.User = value; break;
                case "--password": opt.Password = value; break;
                default: return null;
            }
        }
        return opt;
    }

    static void PrintUsage()
    {
        Console.Error.WriteLine("""
            Использование: dotnet run -- [параметры]
              --host     адрес SMTP-сервера   (по умолчанию localhost)
              --port     порт                 (по умолчанию 25)
              --from     адрес отправителя    (по умолчанию test@localhost)
              --to       адрес получателя     (по умолчанию user@localhost)
              --subject  тема письма          (по умолчанию "Test from SMTP Client")
              --text     текст письма
              --user     логин для AUTH       (если не задан, аутентификация не выполняется)
              --password пароль для AUTH
            """);
    }
}
