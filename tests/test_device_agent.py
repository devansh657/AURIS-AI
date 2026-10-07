import hashlib
import unittest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from auris.device_agent import (
    DeviceAction,
    device_capabilities,
    execute_device_action,
    is_device_command,
    match_device_command,
    match_device_commands,
)
from auris.windows_apps import InstalledApplication


class DeviceAgentTests(unittest.TestCase):
    def test_resolves_compound_application_sequence(self):
        applications = [
            InstalledApplication(
                "Spotify",
                r"C:\Users\Devansh\AppData\Roaming\Spotify\Spotify.exe",
                "test",
                process_names=("spotify.exe",),
            )
        ]

        actions = match_device_commands("AURIS, open Spotify and play music", applications)

        self.assertIsNotNone(actions)
        self.assertEqual([action.kind for action in actions], ["launch_app", "app_media"])
        self.assertEqual(actions[1].target, "Spotify")

    def test_resolves_compound_browser_and_window_sequence(self):
        applications = [
            InstalledApplication(
                "Brave",
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                "test",
                process_names=("brave.exe",),
            )
        ]

        actions = match_device_commands(
            "open YouTube in Brave then maximize Brave", applications
        )

        self.assertIsNotNone(actions)
        self.assertEqual([action.kind for action in actions], ["launch_app", "maximize_app"])
        self.assertTrue(is_device_command("open YouTube in Brave then maximize Brave"))

    def test_compound_sequence_fails_closed_when_any_clause_is_unknown(self):
        applications = [
            InstalledApplication(
                "Spotify", "spotify.exe", "test", process_names=("spotify.exe",)
            )
        ]

        self.assertIsNone(
            match_device_commands("open Spotify and transmit my passwords", applications)
        )

    def test_matches_allowlisted_application(self):
        action = match_device_command("AURIS, open Notepad")

        self.assertIsNotNone(action)
        self.assertEqual(action.action_id, "open_notepad")
        self.assertEqual(action.executable, "notepad.exe")

    def test_accepts_natural_polite_device_phrasing(self):
        for command in (
            "AURIS, could you please open Notepad",
            "Please launch Calculator",
            "I want you to open Paint",
        ):
            with self.subTest(command=command):
                self.assertIsNotNone(match_device_command(command))

    def test_matches_discovered_application_actions(self):
        applications = [
            InstalledApplication(
                "Spotify",
                r"C:\Users\Devansh\AppData\Roaming\Spotify\Spotify.exe",
                "test",
                process_names=("spotify.exe",),
            )
        ]

        opened = match_device_command("AURIS, open Spotify", applications)
        closed = match_device_command("close the Spotify app", applications)
        focused = match_device_command("switch to Spotify", applications)
        minimized = match_device_command("minimise the Spotify window", applications)
        maximized = match_device_command("maximize Spotify", applications)
        restored = match_device_command("restore Spotify window", applications)

        self.assertEqual(opened.kind, "launch_app")
        self.assertEqual(closed.kind, "close_app")
        self.assertEqual(focused.kind, "focus_app")
        self.assertEqual(minimized.kind, "minimize_app")
        self.assertEqual(maximized.kind, "maximize_app")
        self.assertEqual(restored.kind, "restore_app")
        self.assertEqual(opened.process_names, ("spotify.exe",))

    def test_generic_app_intent_is_a_device_command(self):
        self.assertTrue(is_device_command("open Spotify"))
        self.assertTrue(is_device_command("close Discord"))
        self.assertTrue(is_device_command("focus on Word"))
        self.assertTrue(is_device_command("minimize Spotify"))
        self.assertTrue(is_device_command("maximize Notepad"))
        self.assertTrue(is_device_command("restore Edge"))
        self.assertTrue(is_device_command("open my InfraGuard project"))

    def test_opens_allowlisted_destination_in_exact_named_browser(self):
        brave = InstalledApplication(
            "Brave",
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            "test",
            aliases=("Brave Browser",),
            process_names=("brave.exe",),
        )

        action = match_device_command("AURIS, open YouTube on Brave", [brave])

        self.assertEqual(action.kind, "launch_app")
        self.assertEqual(action.arguments, ("https://www.youtube.com/",))
        self.assertIn("url_sha256=", action.target)
        with patch("auris.device_agent.resolve_application", return_value=brave):
            self.assertTrue(is_device_command("open YouTube in Brave"))

    def test_named_browser_supports_public_domains_and_search_but_blocks_private_targets(self):
        brave = InstalledApplication(
            "Brave", r"C:\Brave\brave.exe", "test", process_names=("brave.exe",)
        )

        domain = match_device_command("open github.com in Brave", [brave])
        youtube_search = match_device_command("search YouTube for AURIS demos in Brave", [brave])
        web_search = match_device_command("search the web for local AI assistants using Brave", [brave])

        self.assertEqual(domain.arguments, ("https://github.com",))
        self.assertIn("search_query=AURIS+demos", youtube_search.arguments[0])
        self.assertIn("q=local+AI+assistants", web_search.arguments[0])
        self.assertIsNone(match_device_command("open http://127.0.0.1 in Brave", [brave]))
        self.assertIsNone(match_device_command("open http://localhost in Brave", [brave]))
        self.assertIsNone(match_device_command("open https://example.com/?token=value in Brave", [brave]))
        self.assertIsNone(match_device_command("search web for my password secret token in Brave", [brave]))

    @patch("auris.device_agent._public_web_url_allowed", return_value=True)
    @patch("auris.device_agent._find_application_window", return_value=None)
    @patch("auris.device_agent._running_processes", return_value=[("brave.exe", 44)])
    @patch("auris.device_agent.subprocess.Popen")
    @patch("auris.device_agent.shutil.which")
    def test_named_browser_destination_uses_fixed_argument_list(
        self, which, popen, _processes, _window, _public_url
    ):
        executable = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
        which.return_value = executable
        popen.return_value.pid = 44
        brave = InstalledApplication(
            "Brave", executable, "test", process_names=("brave.exe",)
        )
        action = match_device_command("open YouTube using Brave", [brave])

        result = execute_device_action(action)

        self.assertTrue(result["ok"])
        self.assertTrue(result["launch_arguments_bound"])
        self.assertEqual(popen.call_args.args[0], [executable, "https://www.youtube.com/"])

    def test_targeted_spotify_playback_is_a_composite_device_action(self):
        spotify = InstalledApplication(
            "Spotify", r"C:\Spotify\Spotify.exe", "test", process_names=("spotify.exe",)
        )

        action = match_device_command("AURIS, play songs on Spotify", [spotify])

        self.assertEqual(action.kind, "app_media")
        self.assertEqual(action.key_code, 0xB3)
        with patch("auris.device_agent.resolve_application", return_value=spotify):
            self.assertTrue(is_device_command("play music on Spotify"))

    @patch("auris.device_agent._send_media_key", return_value={"ok": True})
    @patch("auris.device_agent._focus_application", return_value={"ok": True})
    @patch("auris.device_agent._running_processes", return_value=[("spotify.exe", 55)])
    def test_targeted_media_focuses_app_before_play_key(self, _processes, focus, media):
        action = DeviceAction(
            "play_spotify", "app_media", "Play media in Spotify", "Spotify",
            executable=r"C:\Spotify\Spotify.exe", process_names=("spotify.exe",), key_code=0xB3,
        )

        result = execute_device_action(action)

        self.assertTrue(result["ok"])
        self.assertTrue(result["application_focused"])
        self.assertTrue(result["media_key_emitted"])
        self.assertFalse(result["playback_session_observed"])
        focus.assert_called_once_with(action)
        media.assert_called_once_with(action)

    @patch("auris.device_agent._find_application_window", return_value=77)
    @patch("auris.device_agent.ctypes.windll.user32")
    def test_window_state_actions_are_observed_through_win32(self, user32, _find_window):
        application = InstalledApplication(
            "Spotify",
            r"C:\Users\Devansh\Spotify.exe",
            "test",
            process_names=("spotify.exe",),
        )

        user32.IsIconic.return_value = True
        minimized = execute_device_action(match_device_command("minimize Spotify", [application]))
        user32.IsIconic.return_value = False
        user32.IsZoomed.return_value = True
        maximized = execute_device_action(match_device_command("maximize Spotify", [application]))
        user32.IsZoomed.return_value = False
        user32.IsWindowVisible.return_value = True
        restored = execute_device_action(match_device_command("restore Spotify", [application]))

        self.assertTrue(minimized["ok"])
        self.assertEqual(minimized["window_state"], "minimized")
        self.assertTrue(maximized["ok"])
        self.assertEqual(maximized["window_state"], "maximized")
        self.assertTrue(restored["ok"])
        self.assertEqual(restored["window_state"], "restored")
        self.assertEqual(
            [call.args for call in user32.ShowWindow.call_args_list],
            [(77, 6), (77, 3), (77, 9)],
        )

    def test_matches_approved_folder_without_accepting_arbitrary_path(self):
        self.assertEqual(
            match_device_command("Open my Documents").action_id,
            "open_documents",
        )
        self.assertIsNone(match_device_command("Open C:\\Windows\\System32"))

    def test_matches_folder_creation_phrases_as_bounded_device_actions(self):
        named = match_device_command("AURIS, create a folder named DON on Desktop")
        alternate = match_device_command("create new folder and name it Reports in my Documents")
        reordered = match_device_command("create me a folder on my Desktop called Voice Test")

        self.assertIsNotNone(named)
        self.assertEqual(named.kind, "create_folder")
        self.assertEqual(named.path, Path.home() / "Desktop" / "DON")
        self.assertEqual(named.target, str(named.path))
        self.assertEqual(alternate.path, Path.home() / "Documents" / "Reports")
        self.assertEqual(reordered.path, Path.home() / "Desktop" / "Voice Test")
        self.assertTrue(is_device_command("make folder Archive in Downloads"))

    def test_matches_nested_folder_and_note_creation_inside_existing_direct_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop = Path(folder) / "Desktop"
            work = desktop / "Work"
            work.mkdir(parents=True)
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"desktop": desktop}, clear=True):
                folder_action = match_device_command(
                    "create a folder called Notes inside Work on my Desktop"
                )
                note_action = match_device_command(
                    'create a note called Status inside Work on Desktop saying "Ready"'
                )
                folder_result = execute_device_action(folder_action)
                note_result = execute_device_action(note_action)

            self.assertEqual(folder_action.path, work / "Notes")
            self.assertEqual(note_action.path, work / "Status.txt")
            self.assertTrue(folder_result["ok"])
            self.assertTrue(note_result["ok"])
            self.assertTrue((work / "Notes").is_dir())
            self.assertEqual((work / "Status.txt").read_text(encoding="utf-8"), "Ready")

    def test_creation_refuses_more_than_one_existing_parent_level(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop = Path(folder) / "Desktop"
            deep_parent = desktop / "Work" / "Private"
            deep_parent.mkdir(parents=True)
            target = deep_parent / "Too Deep"
            action = DeviceAction(
                "create_folder_too_deep",
                "create_folder",
                "Create folder Too Deep",
                str(target),
                path=target,
                source="approved_user_root",
            )

            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"desktop": desktop}, clear=True):
                result = execute_device_action(action)

            self.assertFalse(result["ok"])
            self.assertFalse(target.exists())
            self.assertIn("one existing direct child", result["error"])

    def test_rejects_unsafe_folder_creation_names_and_locations(self):
        commands = (
            "create folder ../DON on Desktop",
            "create folder nested/DON on Desktop",
            "create folder C:\\Temp on Desktop",
            "create folder CON on Desktop",
            "create folder hidden. on Desktop",
            "create folder DON in C:\\Windows",
        )

        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(match_device_command(command))
                self.assertTrue(is_device_command(command))

    def test_folder_creation_executes_and_verifies_idempotently(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "DON"
            action = DeviceAction(
                "create_folder_desktop_don",
                "create_folder",
                "Create folder DON",
                str(target),
                path=target,
                source="approved_user_root",
            )

            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"desktop": root}, clear=True):
                created = execute_device_action(action)
                repeated = execute_device_action(action)

            self.assertTrue(created["ok"])
            self.assertTrue(created["created"])
            self.assertTrue(target.is_dir())
            self.assertTrue(repeated["ok"])
            self.assertFalse(repeated["created"])
            self.assertEqual(repeated["observed_path"], str(target))

    def test_matches_new_note_with_signed_content_digest(self):
        action = match_device_command(
            'AURIS, create a note called Shopping on Desktop saying "Buy milk"'
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "create_text_file")
        self.assertEqual(action.path, Path.home() / "Desktop" / "Shopping.txt")
        self.assertEqual(action.content, "Buy milk")
        self.assertIn("content_sha256=", action.target)
        self.assertNotIn("Buy milk", action.target)

    def test_rejects_unsafe_or_unsupported_note_targets(self):
        commands = (
            "create a note called ../secret on Desktop saying no",
            "create a text file called payload.exe on Desktop",
            "create a note called CON in Documents",
            "create a note called nested/note in Documents",
            "create a note called note in C:\\Windows",
        )

        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(match_device_command(command))
                self.assertTrue(is_device_command(command))

    def test_note_creation_is_atomic_verified_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "Status.md"
            content = "AURIS is online."
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            action = DeviceAction(
                "create_note_documents_status_md",
                "create_text_file",
                "Create note Status.md",
                f"path={target};content_sha256={digest}",
                path=target,
                content=content,
                source="approved_user_root",
            )
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": root}, clear=True):
                created = execute_device_action(action)
                repeated = execute_device_action(action)
                changed = DeviceAction(
                    action.action_id,
                    action.kind,
                    action.label,
                    f"path={target};content_sha256="
                    + hashlib.sha256(b"changed").hexdigest(),
                    path=target,
                    content="changed",
                    source=action.source,
                )
                refused = execute_device_action(changed)

            self.assertTrue(created["ok"])
            self.assertTrue(created["created"])
            self.assertEqual(target.read_text(encoding="utf-8"), content)
            self.assertTrue(repeated["ok"])
            self.assertFalse(repeated["created"])
            self.assertFalse(refused["ok"])
            self.assertIn("not overwrite", refused["error"])
            self.assertEqual(target.read_text(encoding="utf-8"), content)

    def test_matches_append_with_preimage_and_exact_text_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            documents = Path(folder) / "Documents"
            documents.mkdir()
            note = documents / "Status.txt"
            note.write_text("Initial status", encoding="utf-8")
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": documents}, clear=True):
                action = match_device_command(
                    'AURIS, append "AURIS is operational." to note Status.txt in Documents'
                )

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "append_text_file")
        self.assertEqual(action.content, "AURIS is operational.")
        self.assertIn("pre=", action.target)
        self.assertIn("append=", action.target)
        self.assertNotIn("AURIS is operational", action.target)

    def test_append_is_atomic_verified_and_duplicate_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            documents = Path(folder) / "Documents"
            documents.mkdir()
            note = documents / "Status.txt"
            note.write_text("Initial status", encoding="utf-8")
            command = 'append "AURIS is operational." to note Status.txt in Documents'
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": documents}, clear=True):
                appended = execute_device_action(match_device_command(command))
                repeated = execute_device_action(match_device_command(command))

            self.assertTrue(appended["ok"])
            self.assertTrue(appended["appended"])
            self.assertEqual(note.read_text(encoding="utf-8"), "Initial status\nAURIS is operational.")
            self.assertTrue(repeated["ok"])
            self.assertFalse(repeated["appended"])

    def test_append_refuses_secrets_and_stale_preimage(self):
        with tempfile.TemporaryDirectory() as folder:
            documents = Path(folder) / "Documents"
            documents.mkdir()
            note = documents / "Status.txt"
            note.write_text("Initial status", encoding="utf-8")
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": documents}, clear=True):
                action = match_device_command('append "Next" to note Status.txt in Documents')
                note.write_text("Changed elsewhere", encoding="utf-8")
                stale = execute_device_action(action)
                secret = match_device_command(
                    'append "password is example" to note Status.txt in Documents'
                )

            self.assertFalse(stale["ok"])
            self.assertIn("signed append binding", stale["error"])
            self.assertIsNone(secret)
            self.assertTrue(is_device_command('append "password is example" to note Status.txt in Documents'))
            self.assertEqual(note.read_text(encoding="utf-8"), "Changed elsewhere")

    def test_recycle_file_is_preimage_bound_and_requires_an_existing_safe_file(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop = Path(folder) / "Desktop"
            desktop.mkdir()
            target = desktop / "Old Report.txt"
            target.write_text("recoverable content", encoding="utf-8")
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"desktop": desktop}, clear=True):
                action = match_device_command(
                    'move file "Old Report.txt" from Desktop to the Recycle Bin'
                )
                missing = match_device_command("recycle file Missing.txt from Desktop")

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "recycle_file")
        self.assertEqual(action.path, target)
        self.assertIn("pre=", action.target)
        self.assertIsNone(missing)
        self.assertTrue(is_device_command("recycle file Missing.txt from Desktop"))

    def test_recycle_file_executes_only_for_the_signed_preimage(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop = Path(folder) / "Desktop"
            desktop.mkdir()
            target = desktop / "Old Report.txt"
            target.write_text("recoverable content", encoding="utf-8")

            def recycle(path):
                path.unlink()
                return {"ok": True, "provider": "test_recycle_bin"}

            with (
                patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"desktop": desktop}, clear=True),
                patch("auris.device_agent._send_file_to_recycle_bin", side_effect=recycle) as send,
            ):
                result = execute_device_action(
                    match_device_command("recycle file Old Report.txt from Desktop")
                )

            self.assertTrue(result["ok"])
            self.assertTrue(result["recycled"])
            self.assertTrue(result["source_absent"])
            self.assertFalse(target.exists())
            send.assert_called_once()

    def test_recycle_file_refuses_a_changed_preimage(self):
        with tempfile.TemporaryDirectory() as folder:
            documents = Path(folder) / "Documents"
            documents.mkdir()
            target = documents / "Old.txt"
            target.write_text("first", encoding="utf-8")
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": documents}, clear=True):
                action = match_device_command("recycle file Old.txt from Documents")
                target.write_text("changed", encoding="utf-8")
                with patch("auris.device_agent._send_file_to_recycle_bin") as send:
                    result = execute_device_action(action)

            self.assertFalse(result["ok"])
            self.assertIn("signed Recycle Bin binding", result["error"])
            self.assertTrue(target.exists())
            send.assert_not_called()

    def test_failed_append_readback_restores_exact_preimage(self):
        with tempfile.TemporaryDirectory() as folder:
            documents = Path(folder) / "Documents"
            documents.mkdir()
            note = documents / "Status.txt"
            original = b"Initial status"
            note.write_bytes(original)
            writes = 0

            def corrupt_then_restore(path, content):
                nonlocal writes
                writes += 1
                path.write_bytes(b"corrupt" if writes == 1 else content)

            with (
                patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": documents}, clear=True),
                patch("auris.device_agent._atomic_replace_bytes", side_effect=corrupt_then_restore),
            ):
                result = execute_device_action(
                    match_device_command('append "Next" to note Status.txt in Documents')
                )

            self.assertFalse(result["ok"])
            self.assertTrue(result["rolled_back"])
            self.assertEqual(note.read_bytes(), original)

    def test_matches_bounded_rename_copy_and_move_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = {
                "desktop": root / "Desktop",
                "documents": root / "Documents",
                "downloads": root / "Downloads",
            }
            for location in locations.values():
                location.mkdir()
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", locations, clear=True):
                rename = match_device_command(
                    'AURIS, rename file "Report.txt" in Documents to "Final"'
                )
                copy = match_device_command("copy file Report.txt from Documents to Desktop")
                move = match_device_command(
                    "move Report.txt from Desktop to Downloads as Archived.txt"
                )

        self.assertEqual(rename.kind, "rename_path")
        self.assertEqual(rename.destination.name, "Final.txt")
        self.assertEqual(copy.kind, "copy_file")
        self.assertEqual(copy.destination.name, "Report.txt")
        self.assertEqual(move.kind, "move_file")
        self.assertEqual(move.destination.name, "Archived.txt")
        self.assertTrue(is_device_command("rename folder DON on Desktop to DONE"))

    def test_transfer_parser_rejects_arbitrary_paths_and_unsafe_names(self):
        commands = (
            "rename file ../Report.txt in Documents to Final.txt",
            "copy file C:\\secret.txt from Documents to Desktop",
            "move file Report.txt from C:\\Windows to Desktop",
            "rename folder DON on Desktop to CON",
        )

        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(match_device_command(command))
                self.assertTrue(is_device_command(command))

    def test_copy_move_and_rename_execute_with_hash_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = {
                "desktop": root / "Desktop",
                "documents": root / "Documents",
                "downloads": root / "Downloads",
            }
            for location in locations.values():
                location.mkdir()
            original = locations["documents"] / "Report.txt"
            original.write_text("verified report", encoding="utf-8")
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", locations, clear=True):
                copy_action = match_device_command(
                    "copy file Report.txt from Documents to Desktop"
                )
                copied = execute_device_action(copy_action)
                move_action = match_device_command(
                    "move file Report.txt from Desktop to Downloads as Archived.txt"
                )
                moved = execute_device_action(move_action)
                rename_action = match_device_command(
                    "rename file Report.txt in Documents to Final.txt"
                )
                renamed = execute_device_action(rename_action)

            self.assertTrue(copied["ok"])
            self.assertTrue(moved["ok"])
            self.assertFalse((locations["desktop"] / "Report.txt").exists())
            self.assertEqual(
                (locations["downloads"] / "Archived.txt").read_text(encoding="utf-8"),
                "verified report",
            )
            self.assertTrue(renamed["ok"])
            self.assertFalse(original.exists())
            self.assertEqual(
                (locations["documents"] / "Final.txt").read_text(encoding="utf-8"),
                "verified report",
            )

    def test_nested_copy_rename_and_move_preserve_exact_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            locations = {
                "desktop": root / "Desktop",
                "documents": root / "Documents",
                "downloads": root / "Downloads",
            }
            for location in locations.values():
                location.mkdir()
            work = locations["desktop"] / "Work"
            work.mkdir()
            source = locations["documents"] / "Report.txt"
            source.write_text("nested verified report", encoding="utf-8")

            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", locations, clear=True):
                copied = execute_device_action(
                    match_device_command(
                        "copy file Report.txt from Documents to folder Work on Desktop as Nested.txt"
                    )
                )
                renamed = execute_device_action(
                    match_device_command(
                        "rename file Nested.txt inside Work on Desktop to Renamed.txt"
                    )
                )
                moved = execute_device_action(
                    match_device_command(
                        "move file Renamed.txt from folder Work on Desktop to Downloads as Final.txt"
                    )
                )

            final = locations["downloads"] / "Final.txt"
            self.assertTrue(copied["ok"])
            self.assertTrue(renamed["ok"])
            self.assertTrue(moved["ok"])
            self.assertEqual(final.read_text(encoding="utf-8"), "nested verified report")
            self.assertTrue(source.exists())
            self.assertFalse((work / "Nested.txt").exists())
            self.assertFalse((work / "Renamed.txt").exists())

    def test_transfer_refuses_items_deeper_than_one_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop = Path(folder) / "Desktop"
            documents = Path(folder) / "Documents"
            deep = desktop / "Work" / "Private"
            deep.mkdir(parents=True)
            documents.mkdir()
            source = deep / "Report.txt"
            source.write_text("do not move", encoding="utf-8")
            destination = documents / "Report.txt"
            action = DeviceAction(
                "move_file_too_deep_report",
                "move_file",
                "Move Report.txt",
                f"source={source};destination={destination}",
                path=source,
                destination=destination,
                source="approved_user_root",
            )

            with patch.dict(
                "auris.device_agent.WRITABLE_FOLDERS",
                {"desktop": desktop, "documents": documents},
                clear=True,
            ):
                result = execute_device_action(action)

            self.assertFalse(result["ok"])
            self.assertIn("one-parent-deep", result["error"])
            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())

    def test_copy_refuses_existing_destination_without_changing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source_root = root / "Documents"
            destination_root = root / "Desktop"
            source_root.mkdir()
            destination_root.mkdir()
            (source_root / "Report.txt").write_text("source", encoding="utf-8")
            existing = destination_root / "Report.txt"
            existing.write_text("keep me", encoding="utf-8")
            locations = {"documents": source_root, "desktop": destination_root}
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", locations, clear=True):
                action = match_device_command("copy Report.txt from Documents to Desktop")
                result = execute_device_action(action)

            self.assertFalse(result["ok"])
            self.assertIn("already exists", result["error"])
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep me")

    def test_folder_rename_is_verified_and_signed_path_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            desktop = Path(folder) / "Desktop"
            desktop.mkdir()
            source = desktop / "DON"
            source.mkdir()
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"desktop": desktop}, clear=True):
                action = match_device_command("rename folder DON on Desktop to DONE")
                renamed = execute_device_action(action)
                tampered = DeviceAction(
                    "rename_path_done_other",
                    "rename_path",
                    "Rename DONE to OTHER",
                    action.target,
                    path=desktop / "DONE",
                    destination=desktop / "OTHER",
                    source="approved_user_root",
                )
                refused = execute_device_action(tampered)

            self.assertTrue(renamed["ok"])
            self.assertFalse(source.exists())
            self.assertTrue((desktop / "DONE").is_dir())
            self.assertFalse(refused["ok"])
            self.assertIn("signed filesystem paths", refused["error"])
            self.assertTrue((desktop / "DONE").is_dir())

    def test_matches_safe_open_file_without_treating_apps_as_files(self):
        action = match_device_command('AURIS, open file "Report.pdf" from Documents')

        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "open_file")
        self.assertEqual(action.path, Path.home() / "Documents" / "Report.pdf")
        self.assertIsNone(match_device_command("open payload.exe from Downloads"))
        self.assertTrue(is_device_command("open payload.exe from Downloads"))

    @patch("auris.device_agent._find_window_with_title", return_value=101)
    @patch("auris.device_agent.os.startfile", create=True)
    def test_open_file_requires_safe_direct_file_and_observes_window(self, startfile, _window):
        with tempfile.TemporaryDirectory() as folder:
            documents = Path(folder) / "Documents"
            documents.mkdir()
            report = documents / "Report.pdf"
            report.write_text("verified", encoding="utf-8")
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": documents}, clear=True):
                action = match_device_command("open Report.pdf in Documents")
                result = execute_device_action(action)

            self.assertTrue(result["ok"])
            self.assertEqual(result["window_handle"], 101)
            self.assertEqual(result["observed_path"], str(report))
            startfile.assert_called_once_with(str(report))

    @patch("auris.device_agent._find_window_with_title", return_value=202)
    @patch("auris.device_agent.subprocess.Popen")
    @patch("auris.device_agent.shutil.which", return_value=r"C:\Windows\System32\notepad.exe")
    def test_text_file_open_uses_fixed_notepad_argument_list(self, _which, popen, _window):
        popen.return_value.pid = 303
        with tempfile.TemporaryDirectory() as folder:
            documents = Path(folder) / "Documents"
            documents.mkdir()
            note = documents / "Note.txt"
            note.write_text("verified", encoding="utf-8")
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": documents}, clear=True):
                result = execute_device_action(match_device_command("open Note.txt in Documents"))

            self.assertTrue(result["ok"])
            self.assertEqual(result["process_id"], 303)
            self.assertEqual(popen.call_args.args[0], [r"C:\Windows\System32\notepad.exe", str(note)])

    @patch("auris.device_agent.os.startfile", create=True)
    def test_open_file_rejects_links_and_executable_extensions(self, startfile):
        with tempfile.TemporaryDirectory() as folder:
            documents = Path(folder) / "Documents"
            documents.mkdir()
            executable = documents / "payload.exe"
            executable.write_bytes(b"MZ")
            action = DeviceAction(
                "open_file_documents_payload_exe",
                "open_file",
                "Open file payload.exe",
                str(executable),
                path=executable,
                source="approved_user_root",
            )
            with patch.dict("auris.device_agent.WRITABLE_FOLDERS", {"documents": documents}, clear=True):
                result = execute_device_action(action)

            self.assertFalse(result["ok"])
            startfile.assert_not_called()

    def test_capabilities_are_typed_and_bounded(self):
        capabilities = device_capabilities()

        self.assertGreaterEqual(len(capabilities), 5)
        self.assertTrue(all(set(item) == {"id", "label", "risk"} for item in capabilities))

    @patch("auris.device_agent._is_registered_project_root", return_value=True)
    @patch("auris.device_agent.subprocess.run")
    def test_registered_project_open_observes_exact_explorer_path(self, run, _registered):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run.return_value = subprocess.CompletedProcess(
                [], 0, f'{{"ok":true,"path":"{str(root).replace(chr(92), chr(92) * 2)}","observed":true}}\n', ""
            )
            action = DeviceAction(
                "open_project_sample",
                "open_folder",
                "Open Sample project",
                str(root),
                path=root,
                source="registered_project",
            )

            result = execute_device_action(action)

        self.assertTrue(result["ok"])
        self.assertEqual(result["observed_path"], str(root))
        command = run.call_args.args[0]
        self.assertIsInstance(command, list)
        self.assertEqual(command[-2:], ["-Path", str(root)])


if __name__ == "__main__":
    unittest.main()
