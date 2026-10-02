import Foundation
import Network

final class UdpClient {
    private var connection: NWConnection?

    func connect(host: String, port: UInt16) {
        connection?.cancel()
        let endpointHost = NWEndpoint.Host(host)
        let endpointPort = NWEndpoint.Port(rawValue: port) ?? 5555
        let connection = NWConnection(host: endpointHost, port: endpointPort, using: .udp)
        connection.start(queue: .global(qos: .userInitiated))
        self.connection = connection
    }

    func send(_ data: Data) {
        connection?.send(content: data, completion: .contentProcessed { _ in })
    }

    func close() {
        connection?.cancel()
        connection = nil
    }
}
