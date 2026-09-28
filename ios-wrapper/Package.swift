// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "NeoDrug",
    platforms: [
        .iOS(.v16),
        .macOS(.v14),
    ],
    products: [
        .library(
            name: "App",
            targets: ["App"]
        ),
    ],
    targets: [
        .target(
            name: "App",
            resources: [
                .process("Resources")
            ]
        ),
    ]
)
