import CoreGraphics
import Foundation
if !CGPreflightScreenCaptureAccess() {
    fputs("Screen recording permission is required for the capture helper.\n", stderr)
    exit(2)
}
let windows = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] ?? []
let result = windows.compactMap { w -> [String: Any]? in
    guard let name = w[kCGWindowName as String] as? String,
          let owner = w[kCGWindowOwnerName as String] as? String,
          owner.lowercased() == "onmyoji.exe",
          let id = w[kCGWindowNumber as String] as? Int else { return nil }
    return ["title": name, "id": id]
}
let data = try JSONSerialization.data(withJSONObject: result)
FileHandle.standardOutput.write(data)
