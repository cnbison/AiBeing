// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AiBeing",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "AiBeing",
            path: "Sources",
            resources: [
                .copy("Resources/chat_bg.png"),
                .copy("Resources/persona_engine_viz.html")
            ]
        ),
    ]
)
