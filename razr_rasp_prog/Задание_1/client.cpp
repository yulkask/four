#include <arpa/inet.h>
#include <cerrno>
#include <cstring>
#include <iostream>
#include <string>
#include <sys/socket.h>
#include <unistd.h>

namespace {
constexpr unsigned short kPort = 12789;
constexpr std::size_t kBufferSize = 1024;

bool send_all(int socket_fd, const std::string& message)
{
    std::size_t sent_total = 0;

    while (sent_total < message.size()) {
        const ssize_t sent = send(socket_fd, message.data() + sent_total,
                                  message.size() - sent_total, 0);
        if (sent > 0) {
            sent_total += static_cast<std::size_t>(sent);
        } else if (sent == -1 && errno == EINTR) {
            continue;
        } else {
            return false;
        }
    }
    return true;
}

bool receive_until_close(int socket_fd, std::string& message)
{
    char buffer[kBufferSize];

    for (;;) {
        const ssize_t received = recv(socket_fd, buffer, sizeof(buffer), 0);
        if (received > 0) {
            message.append(buffer, static_cast<std::size_t>(received));
        } else if (received == 0) {
            return true;
        } else if (errno != EINTR) {
            perror("recv");
            return false;
        }
    }
}
} // namespace

int main(int argc, char* argv[])
{
    if (argc > 2) {
        std::cerr << "Использование: " << argv[0] << " [IP_адрес_сервера]\n";
        return 1;
    }

    std::string server_ip;
    if (argc == 2) {
        server_ip = argv[1];
    } else {
        std::cout << "Введите IP-адрес сервера: ";
        if (!std::getline(std::cin, server_ip)) {
            std::cerr << "Не удалось прочитать IP-адрес.\n";
            return 1;
        }
    }

    std::cout << "Введите строку для отправки серверу: ";
    std::string message;
    if (!std::getline(std::cin, message)) {
        std::cerr << "Не удалось прочитать строку.\n";
        return 1;
    }

    const int socket_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (socket_fd == -1) {
        perror("socket");
        return 1;
    }

    sockaddr_in server_address{};
    server_address.sin_family = AF_INET;
    server_address.sin_port = htons(kPort);
    if (inet_pton(AF_INET, server_ip.c_str(), &server_address.sin_addr) != 1) {
        std::cerr << "Некорректный IP-адрес сервера.\n";
        close(socket_fd);
        return 1;
    }
    if (connect(socket_fd, reinterpret_cast<const sockaddr*>(&server_address),
                sizeof(server_address)) == -1) {
        perror("connect");
        close(socket_fd);
        return 1;
    }

    if (!send_all(socket_fd, message)) {
        perror("send");
        close(socket_fd);
        return 1;
    }
    std::cout << "[Клиент] Отправлено: " << message << '\n';

    if (shutdown(socket_fd, SHUT_WR) == -1) {
        perror("shutdown");
        close(socket_fd);
        return 1;
    }

    std::string response;
    if (!receive_until_close(socket_fd, response)) {
        close(socket_fd);
        return 1;
    }
    std::cout << "[Клиент] Получено: " << response << '\n';

    close(socket_fd);
    return 0;
}
