-- logic_transport.applescript
-- Minimal Logic Pro transport control for the intermodulation experiments.
--
-- HONEST SCOPE NOTE (MUZI, 2026-10-22): Logic's AppleScript dictionary is
-- thin and version-dependent — it reliably covers opening a project and
-- basic transport via UI scripting, not deep session construction. The
-- real Experiment 8 session (Track A anchor, Track B sweep, polarity-flip
-- automation at the 22,550 Hz crossing) is built ONCE by hand in Logic
-- from the recipe in README.md, saved as a template project; after that
-- this script opens the template and runs playback unattended.
-- Claude on the Lenovo/Mac side: adapt the UI element names to the Logic
-- version actually installed before relying on this.
--
-- Usage: osascript logic_transport.applescript <path-to-.logicx> [seconds]

on run argv
	set projectPath to item 1 of argv
	set playSeconds to 25
	if (count of argv) > 1 then set playSeconds to (item 2 of argv) as integer

	tell application "Logic Pro"
		activate
		open (POSIX file projectPath)
	end tell

	delay 3 -- let the project load

	-- Start playback (space bar via System Events; Logic must be frontmost)
	tell application "System Events"
		tell process "Logic Pro"
			keystroke " " -- play
		end tell
	end tell

	delay playSeconds

	tell application "System Events"
		tell process "Logic Pro"
			keystroke " " -- stop
		end tell
	end tell
end run
