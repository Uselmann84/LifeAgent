import SwiftUI

/// Persistent, unmistakable banner shown whenever connected to a non-production
/// backend, so demo/development data is never mistaken for production.
struct EnvironmentBanner: View {
    let environment: BackendEnvironment
    let isOffline: Bool

    var body: some View {
        if environment.showsBanner || isOffline {
            HStack(spacing: 8) {
                Image(systemName: isOffline ? "wifi.slash" : "flask")
                    .font(.caption.weight(.bold))
                Text(bannerText)
                    .font(.caption.weight(.semibold))
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
            .background(background)
            .foregroundStyle(.white)
            .accessibilityLabel(Text(bannerText))
        }
    }

    private var bannerText: String {
        if isOffline { return "Backend offline — showing cached data" }
        return "\(environment.displayName) backend — not production data"
    }

    private var background: Color {
        if isOffline { return .gray }
        switch environment {
        case .demo: return .indigo
        case .development: return .orange
        case .staging: return .purple
        case .production: return .clear
        }
    }
}
