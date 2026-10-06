using System.Net.Sockets;
using System.Text;

namespace ChatClient;

static class Program
{
    // Константы протокола, общие для всей аудитории.
    const int DefaultPort = 50001;
    const int MaxLineBytes = 1024;

    static readonly object ConsoleLock = new();
    static readonly object CloseLock = new();
    static Socket _socket = null!;
    static bool _closed;

    static int Main(string[] args)
    {
        Console.InputEncoding = Encoding.UTF8;
        Console.OutputEncoding = Encoding.UTF8;

        // Аргументы: адрес_сервера [ник] [порт]. Недостающее спрашиваем в консоли.
        string host = args.Length > 0 ? args[0] : Ask("IP-адрес сервера (Enter = 127.0.0.1): ", "127.0.0.1");
        string nick = args.Length > 1 ? args[1] : Ask("Ваш ник (1-20 символов, без пробелов): ", "");
        int port = DefaultPort;
        if (args.Length > 2 && (!int.TryParse(args[2], out port) || port is < 1 or > 65535))
        {
            Console.Error.WriteLine("Использование: dotnet run -- <IP сервера> [ник] [порт]");
            return 1;
        }
        if (nick.Length == 0)
        {
            Console.Error.WriteLine("Ник не может быть пустым.");
            return 1;
        }

        try
        {
            _socket = new Socket(SocketType.Stream, ProtocolType.Tcp) { NoDelay = true };
            _socket.Connect(host, port);
        }
        catch (Exception e) when (e is SocketException or ArgumentException)
        {
            Console.Error.WriteLine($"Не удалось подключиться к {host}:{port}: {e.Message}");
            return 1;
        }

        // Ctrl+C: закрываем соединение штатно, сервер разошлёт "*** nick left".
        // Процесс завершается сам после обработчика (e.Cancel остаётся false).
        Console.CancelKeyPress += (_, _) => Close("Отключено (Ctrl+C).");

        Print($"Подключено к {host}:{port}. Команды: /list, /nick новыйник, /msg текст, /quit.");

        // Первая строка протокола - ник.
        if (!SendLine(nick))
            return 1;

        // Сокет читается в отдельном потоке, консоль - в основном: оба работают одновременно.
        new Thread(ReceiveLoop) { IsBackground = true }.Start();

        while (true)
        {
            string? line = Console.ReadLine();
            if (line == null) // конец ввода (Ctrl+D / Ctrl+Z)
            {
                Close("Отключено.");
                return 0;
            }
            line = line.TrimEnd('\r');
            if (line.Trim().Length == 0)
                continue;
            if (line.Trim() == "/quit")
            {
                Close("Отключено.");
                return 0;
            }
            if (!SendLine(line))
                return 1;
        }
    }

    // Читает строки от сервера и выводит их как есть.
    static void ReceiveLoop()
    {
        byte[] buffer = new byte[4096];
        List<byte> pending = new();
        try
        {
            while (true)
            {
                int n = _socket.Receive(buffer);
                if (n == 0)
                    break;
                for (int i = 0; i < n; i++)
                {
                    if (buffer[i] != (byte)'\n')
                    {
                        pending.Add(buffer[i]);
                        continue;
                    }
                    string line = Encoding.UTF8.GetString(pending.ToArray()).TrimEnd('\r');
                    pending.Clear();
                    if (line.Length > 0)
                        Print(line);
                }
            }
        }
        catch (Exception e) when (e is SocketException or ObjectDisposedException)
        {
            lock (CloseLock)
                if (_closed)
                    return; // соединение закрыли мы сами
        }

        lock (CloseLock)
            if (_closed)
                return;
        Print("*** соединение с сервером потеряно");
        Environment.Exit(1);
    }

    static bool SendLine(string line)
    {
        byte[] data = Encoding.UTF8.GetBytes(TruncateUtf8(line, MaxLineBytes) + "\n");
        try
        {
            _socket.Send(data);
            return true;
        }
        catch (Exception e) when (e is SocketException or ObjectDisposedException)
        {
            Print("*** не удалось отправить: соединение с сервером потеряно");
            return false;
        }
    }

    static void Close(string message)
    {
        lock (CloseLock)
        {
            if (_closed)
                return;
            _closed = true;
        }
        try
        {
            _socket.Shutdown(SocketShutdown.Both);
        }
        catch (SocketException) { }
        _socket.Close();
        Print(message);
    }

    // Обрезает строку до maxBytes байт UTF-8, не разрывая многобайтовые символы.
    static string TruncateUtf8(string s, int maxBytes)
    {
        if (Encoding.UTF8.GetByteCount(s) <= maxBytes)
            return s;
        StringBuilder sb = new();
        int bytes = 0;
        foreach (Rune r in s.EnumerateRunes())
        {
            if (bytes + r.Utf8SequenceLength > maxBytes)
                break;
            sb.Append(r.ToString());
            bytes += r.Utf8SequenceLength;
        }
        return sb.ToString();
    }

    static string Ask(string prompt, string defaultValue)
    {
        Console.Write(prompt);
        string? answer = Console.ReadLine()?.Trim();
        return string.IsNullOrEmpty(answer) ? defaultValue : answer;
    }

    static void Print(string line)
    {
        lock (ConsoleLock)
            Console.WriteLine(line);
    }
}
