// swift-tools-version: 6.0
import PackageDescription
let package = Package(
    name: "App-Builder",
    platforms: [
        .iOS("16.0"),
    ],
    dependencies: [
        .package(name: "RootPackage", path: "../.."),
    ],
    targets: [
        .executableTarget(
    name: "App-App",
    dependencies: [
        .product(name: "App", package: "RootPackage"),
    ],
    linkerSettings: [
    .unsafeFlags([
        "-Xlinker", "-rpath", "-Xlinker", "@executable_path/Frameworks",
    ]),
]
)
    ]
)
