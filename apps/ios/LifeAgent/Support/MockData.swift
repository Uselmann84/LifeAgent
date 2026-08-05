import Foundation

/// Deterministic mock content used for previews and as an offline fallback when
/// the backend is unreachable. Mirrors the shapes returned by the backend seeder.
enum MockData {
    static let today = TodayBriefing(
        generatedAt: "2025-01-06T08:00:00Z",
        topPriorities: [
            PriorityItem(id: "p1", title: "Respond to warranty claim",
                         detail: "Manufacturer requested proof of purchase.",
                         priority: "high", dueAt: "2025-01-07T17:00:00Z"),
            PriorityItem(id: "p2", title: "Vehicle registration renewal",
                         detail: "Expires end of month.",
                         priority: "medium", dueAt: "2025-01-31T00:00:00Z"),
            PriorityItem(id: "p3", title: "Reply to accountant",
                         detail: "Tax documents question.",
                         priority: "medium", dueAt: nil),
        ],
        deadlines: [
            DeadlineItem(id: "d1", title: "Insurance renewal", dueAt: "2025-01-15T00:00:00Z"),
        ],
        importantEmail: [
            EmailSummary(id: "e1", sender: "warranty@appliance.example",
                         subject: "Re: Claim #4821", importance: "high"),
        ],
        suggestedActions: [
            "Draft a reply attaching the receipt",
            "Add a reminder to renew registration",
        ]
    )

    static let approval = ApprovalRequest(
        id: "a1",
        actionType: "send_approved_email",
        summary: "Send warranty follow-up to manufacturer",
        externalEffect: "Sends an email to warranty@appliance.example",
        riskLevel: "high",
        target: "warranty@appliance.example",
        payload: [
            "to": AnyCodable("warranty@appliance.example"),
            "subject": AnyCodable("Re: Claim #4821 — proof of purchase attached"),
            "body": AnyCodable("Hello, please find the requested receipt attached. Kind regards."),
        ],
        payloadHash: "demo-hash-0001",
        status: "pending",
        expiresAt: "2025-01-06T09:00:00Z",
        relatedCaseId: "c1"
    )

    static let agentResponse = AgentResponse(
        rationale: "I checked your open cases and the warranty thread.",
        found: ["1 open warranty case", "1 email awaiting your reply"],
        recommendations: ["Attach the receipt and reply today"],
        prepared: ["A draft reply to the manufacturer"],
        requiresApproval: [approval],
        completed: [],
        unverified: [],
        securityWarnings: []
    )

    static let cases = [
        CaseItem(id: "c1", title: "Refrigerator warranty claim", status: "open",
                 desiredOutcome: "Repair or replacement under warranty",
                 nextAction: "Follow up if no reply by Friday",
                 nextFollowupAt: "2025-01-09T00:00:00Z"),
        CaseItem(id: "c2", title: "Vehicle registration", status: "waiting",
                 desiredOutcome: "Renewed registration",
                 nextAction: "Await DMV confirmation", nextFollowupAt: nil),
    ]

    static let activity = [
        ActivityEntry(id: "act1", action: "draft_email",
                      summary: "Prepared a warranty follow-up draft",
                      createdAt: "2025-01-06T07:55:00Z"),
        ActivityEntry(id: "act2", action: "create_case",
                      summary: "Opened case: Refrigerator warranty claim",
                      createdAt: "2025-01-05T14:10:00Z"),
    ]

    static let memory = [
        MemoryItem(id: "m1", content: "Prefers formal tone with institutions.",
                   category: "preference", createdAt: "2025-01-01T00:00:00Z"),
        MemoryItem(id: "m2", content: "Refrigerator purchased Nov 2023, 5-year warranty.",
                   category: "fact", createdAt: "2025-01-01T00:00:00Z"),
    ]
}
