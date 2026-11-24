// Семинар 24.11. Свой traceroute на ICMP-сокете.
//
// Идея traceroute: каждый маршрутизатор уменьшает поле TTL в IP-заголовке на 1.
// Когда TTL становится нулём, маршрутизатор не пересылает пакет дальше, а
// возвращает отправителю ICMP «время истекло» (тип 11) со своего адреса.
// Поэтому пакет с TTL = 1 отвечает первый маршрутизатор, с TTL = 2 — второй,
// и так далее, пока целевой узел не пришлёт обычный ICMP Echo Reply (тип 0).

using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;

// 30 переходов хватает почти для любого маршрута. 
// Таймаут — в миллисекундах - 3000 мс на один переход.
const int DefaultMaxHops = 30;
const int DefaultTimeoutMs = 3000;

// Строка запуска: tracert <хост или IP> [-h число] [-t миллисекунды] [-i интерфейс]
if (!TryParseArgs(args, out var options, out var error))
{
    Console.Error.WriteLine(error);
    PrintUsage();
    return 1;
}

// В пакет кладётся IP, а не имя. Имя сначала спрашиваем у DNS.
IPAddress address;
try
{
    address = ResolveIpv4(options.Host);
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Не удалось разрешить имя {options.Host}: {ex.Message}");
    return 1;
}

Socket socket;
try
{
    socket = OpenIcmpSocket();
    if (options.InterfaceName is not null)
        BindToInterface(socket, options.InterfaceName);
}
catch (Exception ex) when (ex is InvalidOperationException or SocketException)
{
    Console.Error.WriteLine(ex.Message);
    return 1;
}

using var icmp = socket;

Console.WriteLine(
    $"Трассировка до {options.Host} ({address}), максимум {options.MaxHops} переходов, таймаут {options.TimeoutMs} мс");
Console.WriteLine();

// TTL = 1 спрашивает первый маршрутизатор, TTL = 2 — второй, и так далее.
// Цикл обрывается раньше лимита, если пришёл ответ самой цели или «узел недоступен».
var reached = false;
for (var ttl = 1; ttl <= options.MaxHops; ttl++)
{
    var hop = Probe(icmp, address, ttl, options.TimeoutMs);
    Console.WriteLine(FormatHop(ttl, hop));

    // Echo Reply — пакет дошёл до цели. Destination Unreachable — маршрут оборвался.
    // Звезда и обычный промежуточный узел цикл не останавливают.
    if (hop.Kind is HopKind.Reached or HopKind.Unreachable)
    {
        reached = hop.Kind == HopKind.Reached;
        break;
    }
}

// Сюда попадаем и по звёздам до конца лимита, и если сеть ответила «недоступен».
if (!reached)
    Console.WriteLine("Цель не ответила в пределах заданного числа переходов.");

return 0;

static Socket OpenIcmpSocket()
{
    // Ядро само подставляет контрольную сумму и доставляет ответ на этот сокет.
    // Полноценный RAW-сокет здесь требует прав администратора (на этой машине он не открылся).
    try
    {
        return new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Icmp);
    }
    catch (SocketException)
    {
        try
        {
            return new Socket(AddressFamily.InterNetwork, SocketType.Raw, ProtocolType.Icmp);
        }
        catch (SocketException ex)
        {
            throw new InvalidOperationException(
                "Не удалось открыть ICMP-сокет. На Windows для RAW-сокета нужны права администратора. " + ex.Message,
                ex);
        }
    }
}

static void BindToInterface(Socket socket, string interfaceName)
{
    // В условии такого ключа нет. Он нужен на машине, где маршрут по умолчанию
    // уходит в VPN: пакеты тогда живы, но ICMP-ответы в туннель не возвращаются.
    if (!OperatingSystem.IsMacOS())
        throw new InvalidOperationException("Параметр -i поддерживается на macOS: там его просит VPN, перехвативший маршрут по умолчанию.");

    // if_nametoindex("en0") даёт номер интерфейса. Ноль значит, что такого имени нет.
    var index = Native.if_nametoindex(interfaceName);
    if (index == 0)
        throw new InvalidOperationException($"Интерфейс {interfaceName} не найден.");

    // IP_BOUND_IF = 25 в netinet/in.h. Без этого пакет уходит в туннель VPN (utun)
    // и ответы ICMP не возвращаются, хотя сеть при этом жива.
    socket.SetRawSocketOption((int)SocketOptionLevel.IP, 25, BitConverter.GetBytes(index));
}

static Hop Probe(Socket socket, IPAddress destination, int ttl, int timeoutMs)
{
    // Один и тот же номер пакета кладём в ICMP Sequence, чтобы отличить свой ответ
    // от чужого, если на сокет придёт постороннее ICMP-сообщение.
    // Номер перехода становится номером пакета. Ответ с другим Sequence — не наш.
    var sequence = (ushort)ttl;
    var packet = BuildEchoRequest(sequence);

    // IP_TTL записывается в заголовок IP, не в ICMP. Именно его уменьшают маршрутизаторы.
    socket.SetSocketOption(SocketOptionLevel.IP, SocketOptionName.IpTimeToLive, ttl);

    // У ICMP нет порта, поэтому в адресе назначения порт 0. Адрес — всегда конечная цель,
    // а не очередной маршрутизатор: маршрутизатор мы заранее не знаем, его выдаст ответ.
    var destinationEndPoint = new IPEndPoint(destination, 0);
    var sentAt = Stopwatch.GetTimestamp();
    socket.SendTo(packet, destinationEndPoint);

    // Таймаут считается от отправки, а не заново на каждый принятый пакет:
    // лишние ICMP не должны растягивать ожидание этого перехода.
    var deadline = TimeSpan.FromMilliseconds(timeoutMs);
    while (Stopwatch.GetElapsedTime(sentAt) < deadline)
    {
        var remaining = deadline - Stopwatch.GetElapsedTime(sentAt);
        socket.ReceiveTimeout = Math.Max(1, (int)remaining.TotalMilliseconds);

        // 512 байт хватает: нам нужен ICMP-заголовок и вложенные в него 28 байт исходного пакета.
        var buffer = new byte[512];
        EndPoint from = new IPEndPoint(IPAddress.Any, 0);
        int received;
        try
        {
            // ReceiveFrom заодно сообщает, кто прислал пакет. Для типа 11 это и есть адрес перехода.
            received = socket.ReceiveFrom(buffer, ref from);
        }
        catch (SocketException ex) when (ex.SocketErrorCode == SocketError.TimedOut)
        {
            // За оставшееся время ответа не было. Это звезда в таблице, не ошибка программы.
            break;
        }

        var elapsed = Stopwatch.GetElapsedTime(sentAt);
        // Чужой или обрезанный пакет пропускаем и ждём дальше, пока не вышел общий срок.
        if (!TryReadIcmp(buffer.AsSpan(0, received), sequence, out var kind))
            continue;

        var responder = ((IPEndPoint)from).Address;
        return new Hop(kind, responder, elapsed);
    }

    return new Hop(HopKind.Timeout, null, TimeSpan.Zero);
}

static byte[] BuildEchoRequest(ushort sequence)
{
    // Заголовок ICMP Echo, 8 байт, затем 8 байт данных. Раскладка:
    //   0      тип: 8 — это Echo Request (запрос, как у ping)
    //   1      код: у запроса всегда 0
    //   2..3   контрольная сумма, пока нули: её считают по всему пакету и записывают ниже
    //   4..5   Identifier. На датаграммном сокете macOS ядро это поле затирает,
    //          поэтому чужой ответ по нему не отсечь
    //   6..7   Sequence. Это поле ядро не трогает, сюда кладём номер перехода
    //   8..15  произвольные данные. Они не разбираются, но доказывают, что вернулся наш пакет
    var packet = new byte[16];
    packet[0] = 8;
    packet[1] = 0;
    System.Buffers.Binary.BinaryPrimitives.WriteUInt16BigEndian(packet.AsSpan(4), (ushort)(Environment.ProcessId & 0xFFFF));
    System.Buffers.Binary.BinaryPrimitives.WriteUInt16BigEndian(packet.AsSpan(6), sequence);
    "TRACERT!"u8.CopyTo(packet.AsSpan(8));

    // Сумма считается, пока байты 2 и 3 ещё нули. Результат пишется старшим байтом вперёд.
    var checksum = InternetChecksum(packet);
    packet[2] = (byte)(checksum >> 8);
    packet[3] = (byte)(checksum & 0xFF);
    return packet;
}

static bool TryReadIcmp(ReadOnlySpan<byte> datagram, ushort sequence, out HopKind kind)
{
    kind = HopKind.Timeout;

    // Датаграммный ICMP-сокет macOS отдаёт ответ вместе с IP-заголовком (первый байт 0x45).
    // Если заголовка нет, сообщение начинается сразу с типа ICMP.
    var icmp = datagram;
    if (datagram.Length >= 1 && datagram[0] >> 4 == 4)
    {
        // Старшие 4 бита первого байта — версия IP. Младшие 4 — длина заголовка в словах по 4 байта.
        // У обычного заголовка без опций это 5, то есть 20 байт. ICMP начинается сразу за ним.
        var headerLength = (datagram[0] & 0x0F) * 4;
        if (datagram.Length < headerLength + 8)
            return false;
        icmp = datagram[headerLength..];
    }

    if (icmp.Length < 8)
        return false;

    var type = icmp[0];
    // Тип 0 — Echo Reply. Его шлёт только конечный узел, и Sequence у него лежит
    // прямо в заголовке, на байтах 6–7, без вложенного пакета.
    if (type == 0 && ReadSequence(icmp) == sequence)
    {
        kind = HopKind.Reached;
        return true;
    }

    if (type == 3)
    {
        // Сеть, узел или порт недоступны. Дальше идти некуда.
        kind = HopKind.Unreachable;
        return true;
    }

    if (type == 11 && QuotedSequence(icmp) == sequence)
    {
        // Тип 11: маршрутизатор исчерпал TTL и вернул начало нашего пакета.
        kind = HopKind.Intermediate;
        return true;
    }

    return false;
}

// Sequence в ICMP — двухбайтовое число в сетевом порядке: старший байт идёт первым.
static ushort ReadSequence(ReadOnlySpan<byte> icmp) =>
    System.Buffers.Binary.BinaryPrimitives.ReadUInt16BigEndian(icmp[6..8]);

static ushort? QuotedSequence(ReadOnlySpan<byte> timeExceeded)
{
    // После 8 байт заголовка ICMP Time Exceeded лежит исходный IP-заголовок
    // и первые 8 байт нашего Echo Request. Sequence там на смещении 6.
    if (timeExceeded.Length < 8 + 20)
        return null;

    var quotedIp = timeExceeded[8..];
    if (quotedIp[0] >> 4 != 4)
        return null;

    var headerLength = (quotedIp[0] & 0x0F) * 4;
    if (quotedIp.Length < headerLength + 8)
        return null;

    return ReadSequence(quotedIp[headerLength..]);
}

static ushort InternetChecksum(ReadOnlySpan<byte> data)
{
    // Контрольная сумма RFC 1071, ей же пользуется IP и ICMP.
    // Байты складываются парами в 16-битные слова. Если сумма не влезает в 16 бит,
    // старшие биты прибавляются к младшим. В пакет пишется побитовое отрицание:
    // у получателя сумма всего сообщения вместе с этим полем обязана дать ноль.
    uint sum = 0;
    var i = 0;
    for (; i + 1 < data.Length; i += 2)
        sum += (uint)((data[i] << 8) | data[i + 1]);
    if (i < data.Length)
        sum += (uint)(data[i] << 8);

    while ((sum >> 16) != 0)
        sum = (sum & 0xFFFF) + (sum >> 16);

    return (ushort)~sum;
}

static string FormatHop(int ttl, Hop hop)
{
    // Номер перехода — это тот TTL, с которым уходил запрос.
    var index = ttl.ToString().PadLeft(2);
    // Звезда значит «за таймаут никто не ответил». Так молчат некоторые маршрутизаторы
    // и файрволы: пакет они, может, и переслали, но ICMP обратно не прислали.
    if (hop.Kind == HopKind.Timeout || hop.Address is null)
        return $" {index}    *";

    var time = $"{hop.Roundtrip.TotalMilliseconds,6:0} мс";
    var note = hop.Kind switch
    {
        HopKind.Reached => "  цель достигнута",
        HopKind.Unreachable => "  узел недоступен",
        _ => ""
    };
    return $" {index}  {time}   {hop.Address}{note}";
}

static IPAddress ResolveIpv4(string host)
{
    // Числовой адрес не гоняем через DNS. Программа работает только с IPv4:
    // заголовок, который мы разбираем в ответе, — это заголовок IPv4.
    if (IPAddress.TryParse(host, out var parsed))
    {
        if (parsed.AddressFamily != AddressFamily.InterNetwork)
            throw new InvalidOperationException("нужен адрес IPv4");
        return parsed;
    }

    // У одного имени бывает несколько адресов. Берём первый IPv4.
    var addresses = Dns.GetHostAddresses(host);
    var ipv4 = addresses.FirstOrDefault(item => item.AddressFamily == AddressFamily.InterNetwork);
    if (ipv4 is null)
        throw new InvalidOperationException("у имени нет адреса IPv4");
    return ipv4;
}

static bool TryParseArgs(string[] args, out Options options, out string? error)
{
    options = new Options("", DefaultMaxHops, DefaultTimeoutMs, null);
    error = null;
    if (args.Length == 0)
    {
        error = "Не указан узел.";
        return false;
    }

    string? host = null;
    var maxHops = DefaultMaxHops;
    var timeoutMs = DefaultTimeoutMs;
    string? interfaceName = null;

    // Ключи идут в любом порядке. Всё, что не начинается с «-», — это узел, и он один.
    for (var i = 0; i < args.Length; i++)
    {
        switch (args[i])
        {
            case "-h":
                // TTL — один байт, поэтому больше 255 переходов протокол не выразит.
                if (!TryTakeNumber(args, ref i, 1, 255, "число переходов", out maxHops, out error))
                    return false;
                break;
            case "-t":
                // Верхняя граница 60 секунд, чтобы опечатка не заставила ждать часами.
                if (!TryTakeNumber(args, ref i, 1, 60_000, "таймаут в миллисекундах", out timeoutMs, out error))
                    return false;
                break;
            case "-i":
                if (i + 1 >= args.Length)
                {
                    error = "После -i нужно имя интерфейса, например en0.";
                    return false;
                }
                interfaceName = args[++i];
                break;
            default:
                if (args[i].StartsWith('-') || host is not null)
                {
                    error = $"Неизвестный аргумент: {args[i]}";
                    return false;
                }
                host = args[i];
                break;
        }
    }

    if (host is null)
    {
        error = "Не указан узел.";
        return false;
    }

    options = new Options(host, maxHops, timeoutMs, interfaceName);
    return true;
}

static bool TryTakeNumber(string[] args, ref int index, int min, int max, string name, out int value, out string? error)
{
    value = 0;
    error = null;
    if (index + 1 >= args.Length || !int.TryParse(args[index + 1], out value) || value < min || value > max)
    {
        error = $"Параметр {args[index]} ожидает {name} от {min} до {max}.";
        return false;
    }

    index++;
    return true;
}

static void PrintUsage()
{
    Console.Error.WriteLine("Использование: tracert <хост или IP> [-h число_переходов] [-t таймаут_мс] [-i интерфейс]");
    Console.Error.WriteLine($"По умолчанию переходов {DefaultMaxHops}, таймаут {DefaultTimeoutMs} мс.");
    Console.Error.WriteLine("Таймаут задаётся в миллисекундах. -i нужен, если маршрут по умолчанию уходит в VPN.");
}

static class Native
{
    // Имя интерфейса (en0) превращается в номер, который понимает setsockopt.
    [DllImport("libc", CharSet = CharSet.Ansi)]
    public static extern uint if_nametoindex(string ifname);
}

enum HopKind
{
    Timeout,       // за таймаут ответа не было, в таблице будет *
    Intermediate,  // ICMP тип 11, ответил промежуточный маршрутизатор
    Reached,       // ICMP тип 0, ответила сама цель
    Unreachable    // ICMP тип 3, сеть или узел сообщили, что доставки не будет
}

readonly record struct Hop(HopKind Kind, IPAddress? Address, TimeSpan Roundtrip);

readonly record struct Options(string Host, int MaxHops, int TimeoutMs, string? InterfaceName);
