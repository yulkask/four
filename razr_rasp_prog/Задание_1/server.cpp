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
constexpr std::size_t kMaxMessageSize = 64 * 1024;

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

bool receive_message(int socket_fd, std::string& message)
{
    char buffer[kBufferSize];

    for (;;) {
        const ssize_t received = recv(socket_fd, buffer, sizeof(buffer), 0);
        if (received > 0) {
            if (message.size() + static_cast<std::size_t>(received) > kMaxMessageSize) {
                std::cerr << "Ошибка: сообщение клиента больше " << kMaxMessageSize << " байт.\n";
                return false;
            }
            message.append(buffer, static_cast<std::size_t>(received));
        } else if (received == 0) {
            return true; // Клиент закончил отправку: это конец одного сообщения.
        } else if (errno != EINTR) {
            perror("recv");
            return false;
        }
    }
}
} // namespace

int main()
{
    const int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd == -1) {
        perror("socket");
        return 1;
    }

    int reuse_address = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &reuse_address,
                   sizeof(reuse_address)) == -1) {
        perror("setsockopt");
        close(server_fd);
        return 1;
    }

    sockaddr_in server_address{};
    server_address.sin_family = AF_INET;
    server_address.sin_addr.s_addr = htonl(INADDR_ANY);
    server_address.sin_port = htons(kPort);

    if (bind(server_fd, reinterpret_cast<const sockaddr*>(&server_address),
             sizeof(server_address)) == -1) {
        perror("bind");
        close(server_fd);
        return 1;
    }
    if (listen(server_fd, SOMAXCONN) == -1) {
        perror("listen");
        close(server_fd);
        return 1;
    }

    std::cout << "Сервер запущен на порту " << kPort << ". Для остановки нажмите Ctrl+C.\n";

    for (;;) {
        sockaddr_in client_address{};
        socklen_t client_address_size = sizeof(client_address);
        const int client_fd = accept(server_fd, reinterpret_cast<sockaddr*>(&client_address),
                                     &client_address_size);
        if (client_fd == -1) {
            if (errno == EINTR) {
                continue;
            }
            perror("accept");
            break;
        }

        char client_ip[INET_ADDRSTRLEN]{};
        inet_ntop(AF_INET, &client_address.sin_addr, client_ip, sizeof(client_ip));
        std::cout << "Подключился клиент " << client_ip << ':'
                  << ntohs(client_address.sin_port) << ".\n";

        std::string received_message;
        if (receive_message(client_fd, received_message)) {
            std::cout << "[Сервер] Получено: " << received_message << '\n';

            const std::string response = received_message + " Привет от сервера!";
            if (send_all(client_fd, response)) {
                std::cout << "[Сервер] Отправлено: " << response << '\n';
            } else {
                perror("send");
            }
        }

        close(client_fd);
    }

    close(server_fd);
    return 1;
}
