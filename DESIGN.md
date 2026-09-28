# Waypoint DESIGN.md — Aurora Ink

## World
Premium B2B SaaS: light canvas, deep ink, indigo accent. Stripe marketing atmosphere + Linear product craft. Not purple-on-white AI default; not cream+terracotta.

## Palette
| Role | Value |
|------|--------|
| Ink | `#070B14` |
| Muted | `#5B6478` |
| Canvas | `#F3F6FB` |
| Surface | `#FFFFFF` |
| Hairline | `#E2E8F0` |
| Accent | `#5B54FF` |
| Accent deep | `#3D36CC` |
| Ember (approval urgency) | `#E85D4C` |
| Success | `#059669` |

Legacy Tailwind `coral` / `gold` map to Accent so existing classes inherit the system.

## Type
- Sans: Plus Jakarta Sans (UI)
- Serif: Fraunces — one italic phrase in marketing/dashboard heroes only

## Components
- Buttons: pill, accent primary, ember for destructive/urgent seal actions
- Cards: 14–16px radius, border **or** soft shadow (not both stacked loudly)
- Empty states: always include a working next-step action
- No decorative inert buttons

## Motion
- Hero/demo: staggered rise-in, demo tab crossfade
- Respect `prefers-reduced-motion`
- One focal product frame on marketing; 3D only as optional background (not primary)

## App chrome
Sticky top nav, command palette ⌘K, approval badge, account menu — all destinations must resolve.
