// Free on-device OCR with Apple's Vision framework, used by safezone.py on a Mac.
// swift ocr_vision.swift <img1.png> [img2.png ...]  ->  one JSON line per image:
// {"file": "...", "w": W, "h": H, "boxes": [[x0, y0, x1, y1, "text", confidence], ...]}   (pixels, top-left origin)
import Foundation
import Vision
import AppKit

for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("{\"file\": \"\(path)\", \"error\": \"cannot read\"}"); continue
    }
    let W = Double(cg.width), H = Double(cg.height)
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try? handler.perform([req])
    var out: [[Any]] = []
    for obs in (req.results ?? []) {
        guard let cand = obs.topCandidates(1).first else { continue }
        let b = obs.boundingBox
        out.append([b.minX * W, (1 - b.maxY) * H, b.maxX * W, (1 - b.minY) * H, cand.string, cand.confidence])
    }
    let obj: [String: Any] = ["file": path, "w": W, "h": H, "boxes": out]
    if let data = try? JSONSerialization.data(withJSONObject: obj), let s = String(data: data, encoding: .utf8) { print(s) }
}
