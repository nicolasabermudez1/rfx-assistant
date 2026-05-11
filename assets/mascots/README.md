# The Things — Centrica mascots

Drop transparent-background PNG files (≈ 600 px tall) here. The app's
`things.show()` component picks them up automatically. Until they are
dropped in, the app falls back to a stylised SVG silhouette.

| Filename                        | Used when                                       | Pose in source images |
|---------------------------------|-------------------------------------------------|------------------------|
| `thing_phone.png`               | Email / chase / chat-with-the-agent moments    | Thing holding a phone  |
| `thing_glasses_vacuum.png`      | "Working / cleaning your data" empty states    | Glasses + vacuum + small Thing |
| `thing_family.png`              | Pipeline-complete celebrations                  | Group of Things        |
| `thing_wave.png` *(optional)*   | Generic greeting (top banner)                   | Wave / smile           |
| `thing_question.png` *(optional)* | Open agent question to the user               | Tilted head / curious  |

The component is in [src/rfx_assistant/ui/things.py](../../src/rfx_assistant/ui/things.py).
File-name detection is done in `POSE_FILES` — adjust there if you want
different filenames.
