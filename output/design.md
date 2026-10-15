# Campus Customs Dashboard Design

The dashboard is a small shop's daily desk: a navy workspace rail, warm paper background, serif headings and restrained green, gold and violet role colors. It echoes a campus shop and a ledger rather than a generic chat app. The primary task is to select a ticket, understand the team's work and make a payment decision.

The top row keeps checking cash and completion visible. Tickets remain in a narrow left column while the selected ticket occupies the larger right panel. The request stays above the activity, so the operator can compare what the team does against the actual need. Rent is selected initially because it is a fixed, near-term obligation; the user can choose any ticket.

Each role has a labeled avatar and a consistent color. Labels and initials carry the meaning as well as color. Live events show who delegated, which tools were called and actual results, with JSON details behind expandable controls. The view scrolls within the event stream rather than making the entire desk grow indefinitely. Team summary and Customer draft tabs provide a quieter view after the run.

Approval requests appear above those tabs in a warm gold panel. The operator sees the exact amount and checking balance after payment before opening the confirmation step. That step shows the approver name and a button stating the exact payment amount. A completed payment becomes a receipt. Agents cannot dismiss this step or use the private execution tool. Continue ticket is explicit after a decision, so the user can see the payment result before agents continue.

Resolved tickets use a green label and disable the run button. Resolution means desk handling is complete; the saved decision and draft describe any remaining delivery or customer action. No visual claims that a draft was sent or that a paid purchase was physically received.

The interface uses responsive CSS: the sidebar shrinks on tablets and disappears on phones, the three ticket cards become a compact row, and the work panel moves below them. Buttons have accessible names, visible keyboard focus and disabled states. Reduced-motion preferences suppress animation. The reset dialog starts focus on Keep working and describes what a reset replaces. All shop facts are loaded from the backend; there are no fallback balances or fabricated agent messages.

Typography uses DM Sans and Libre Caslon Display when available, with system and Georgia fallbacks. All essential functionality remains local if those optional font requests fail. The browser polls sequentially every 1.5 seconds, cleans up on unmount, and resets its event cursor when a new shop session begins. No frontend secret or approval capability is exposed.
