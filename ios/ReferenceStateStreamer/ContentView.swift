import SwiftUI

struct ContentView: View {
    @StateObject private var streamer = ReferenceStateStreamer()
    @State private var host = "192.168.1.100"
    @State private var port = "5555"

    var body: some View {
        NavigationStack {
            Form {
                Section("UDP Target") {
                    TextField("PC IP", text: $host)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("Port", text: $port)
                        .keyboardType(.numberPad)
                }

                Section("Status") {
                    LabeledContent("Streaming", value: streamer.isRunning ? "yes" : "no")
                    LabeledContent("Sequence", value: "\(streamer.sequence)")
                    LabeledContent("Tracking", value: streamer.trackingState)
                    LabeledContent("Last error", value: streamer.lastError)
                }

                Button(streamer.isRunning ? "Stop" : "Start") {
                    if streamer.isRunning {
                        streamer.stop()
                    } else {
                        streamer.start(host: host, port: UInt16(port) ?? 5555)
                    }
                }
            }
            .navigationTitle("Reference State")
        }
    }
}
