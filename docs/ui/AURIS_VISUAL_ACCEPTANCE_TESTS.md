# AURIS Visual Acceptance Tests

- No horizontal overflow at desktop or 390-pixel mobile width.
- Command, device, memory, approval, and activity views remain reachable.
- Voice and emergency states are visible in text and colour.
- No control overlaps the transcript or fixed command dock.
- Reduced-motion mode preserves all information.
- Canvas renders nonblank pixels and changes appearance by state.
- Browser console contains no errors during command execution.
- Sensitive operations visibly enter approval state before execution.
- A verified repair approval shows proposal identity, diagnosis, files, diff statistics, targeted/full gate status, and the exact escaped diff before the approve-once control.
- Engineering root, architecture, and review states remain legible at desktop and mobile widths without exposing a project-code execution control for untrusted roots.
- Engineering repair controls disable outside the fixed trusted AURIS root; proposal, application, rejection, and rollback states remain distinguishable without colour alone.
- Registered project cards expose one bounded open command while unregistered projects keep that control unavailable.
- Approval completion renders the exact Windows interaction, observation class, signature status, permission scope, and nonce state without exposing content digests.
