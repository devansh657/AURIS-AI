import unittest
from pathlib import Path
from unittest.mock import patch

from auris.device_agent import DeviceAction
from auris.browser_agent import BrowserAction, BrowserStep
from auris.communications_agent import CommunicationRequest
from auris.project_agent import ProjectOpenRequest
from auris.runtime import (
    CommandContext,
    _execute_approved_supported,
    _execute_supported,
    _memory_command,
    _response_latency_tier,
    process_command,
)
from auris.schemas import TaskState


class RuntimeTests(unittest.TestCase):
    @patch("auris.runtime._model_response")
    def test_common_conversation_uses_instant_kernel_without_model_wait(self, model_response):
        result, state = _execute_supported(
            {"task_id": "task", "task_type": "general_assistance"},
            "AURIS, hello",
            "auris-one",
            False,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["intelligence"]["provider"], "auris_instant_kernel")
        self.assertEqual(result["intelligence"]["duration_ms"], 0)
        self.assertEqual(result["intelligence"]["route"], "instant")
        model_response.assert_not_called()

    def test_response_router_limits_fast_model_to_low_stakes_dialogue(self):
        self.assertEqual(_response_latency_tier("AURIS, tell me a joke", "command"), "fast")
        self.assertEqual(_response_latency_tier("AURIS, tell me a joke", "private"), "fast")
        self.assertEqual(
            _response_latency_tier("AURIS, I have had a difficult day", "command"),
            "fast",
        )
        self.assertEqual(_response_latency_tier("Calculate 17 times 23", "command"), "quality")
        self.assertEqual(_response_latency_tier("Research the latest AI law", "command"), "quality")
        self.assertEqual(_response_latency_tier("Tell me a joke", "discussion"), "quality")
        self.assertEqual(
            _response_latency_tier("I feel chest pain and this is an emergency", "command"),
            "quality",
        )

    def test_memory_command_parses_typed_store_and_retrieval(self):
        decision = _memory_command("AURIS, record decision [hosting provider] Use provider B")
        retrieval = _memory_command("AURIS, what do you remember about hosting?")

        self.assertEqual(decision.operation, "store")
        self.assertEqual(decision.category, "decision")
        self.assertEqual(decision.subject_key, "hosting provider")
        self.assertEqual(decision.content, "Use provider B")
        self.assertEqual(retrieval.operation, "retrieve")
        self.assertEqual(retrieval.query, "hosting?")

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.index_memory", return_value={"ok": True})
    @patch("auris.runtime.store_memory")
    def test_memory_store_reports_conflict_without_silent_overwrite(
        self, store, _index, record_event
    ):
        store.return_value = {
            "ok": True,
            "memory": {
                "memory_id": "memory-new",
                "category": "project",
                "project_id": "auris-one",
            },
            "duplicate": False,
            "conflicts": [{"conflict_id": "conflict"}],
            "requires_resolution": True,
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "memory"},
            "AURIS, remember that [backend port] backend port is 8001",
            "auris-one",
            False,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertTrue(result["requires_resolution"])
        self.assertIn("will not choose", result["message"])
        self.assertEqual(store.call_args.kwargs["subject_key"], "backend port")
        self.assertFalse(record_event.call_args.args[1].get("content_stored_in_audit", False))

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.semantic_search_memories")
    def test_memory_retrieval_marks_stale_and_conflicting_evidence(self, search, _record_event):
        search.return_value = [
            {
                "memory_id": "one",
                "content": "Backend port is 8000",
                "requires_resolution": True,
                "temporal_state": "current",
            },
            {
                "memory_id": "two",
                "content": "Deployment host is old",
                "requires_resolution": False,
                "temporal_state": "stale",
            },
        ]

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "memory"},
            "what do you remember about deployment",
            "auris-one",
            False,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["memory_warning"]["unresolved_conflicts"], 1)
        self.assertEqual(result["memory_warning"]["stale_records"], 1)
        self.assertTrue(result["memory_warning"]["consequential_use_requires_verification"])

    def test_process_command_creates_exact_diff_approval_after_verified_proposal(self):
        proposal_result = {
            "message": "Verified proposal ready.",
            "verification": "Targeted and complete isolated tests passed.",
            "coding_action": {
                "ok": True,
                "operation": "prepare_repair",
                "approval_required": True,
                "proposal": {
                    "proposal_id": "proposal-id",
                    "project_name": "AURIS One",
                    "files": [{"path": "auris/example.py"}],
                    "diff_stats": {"added_lines": 1, "removed_lines": 1},
                },
            },
        }
        with (
            patch("auris.runtime.get_control_state", return_value={"stopped": False}),
            patch("auris.runtime.ensure_conversation"),
            patch("auris.runtime.append_message"),
            patch("auris.runtime.save_task"),
            patch("auris.runtime.prepare_workflow"),
            patch(
                "auris.runtime.execute_workflow",
                return_value=(proposal_result, TaskState.AWAITING_APPROVAL),
            ),
            patch("auris.runtime.update_task_state") as update_task,
            patch("auris.runtime.create_approval") as create_approval,
            patch("auris.runtime.record_event"),
            patch("auris.runtime._save_assistant_message"),
            patch("auris.runtime.get_workflow_run", return_value=None),
        ):
            create_approval.return_value = {"approval_id": "approval-id", "status": "pending"}

            response = process_command(
                "AURIS, fix this failing test", CommandContext(project_id="auris-one", mode="coding")
            )

        self.assertEqual(response["plan"]["state"], TaskState.AWAITING_APPROVAL.value)
        self.assertEqual(response["approval"]["approval_id"], "approval-id")
        self.assertEqual(create_approval.call_args.kwargs["target"], "AURIS One")
        self.assertIn("proposal-id", create_approval.call_args.kwargs["data_summary"])
        self.assertIn("auris/example.py", create_approval.call_args.kwargs["data_summary"])
        update_task.assert_called_once()

    @patch("auris.runtime.execute_ui_control_request")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.build_ui_control_action")
    @patch("auris.runtime.match_ui_control_command")
    @patch("auris.runtime.match_typing_command", return_value=None)
    def test_approved_ui_control_uses_signed_fabric_and_observation(
        self, _typing, match_ui, build_action, authorize, execute
    ):
        request = object()
        action = DeviceAction(
            "invoke_notepad_file",
            "invoke_control",
            "Invoke File in Notepad",
            "app=notepad;control_sha256=digest",
        )
        match_ui.return_value = request
        build_action.return_value = (action, None)
        authorize.return_value = {
            "ok": True,
            "command_id": "command",
            "device_id": "device",
            "permission_scope": "invoke_control",
            "signature_verified": True,
            "nonce_claimed": True,
        }
        execute.return_value = {
            "ok": True,
            "message": "Observed.",
            "verification": "Exact control and UI change observed.",
            "observed": True,
        }

        result, state = _execute_approved_supported(
            {
                "task_id": "task",
                "task_type": "computer_interaction",
                "objective": 'click "File" in Notepad',
            }
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertTrue(result["interaction_action"]["command_fabric"]["signature_verified"])
        authorize.assert_called_once_with(action)

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.execute_device_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.match_device_command")
    def test_approved_recycle_action_uses_signed_fabric_and_observation(
        self, match_device, authorize, execute, record_event
    ):
        action = DeviceAction(
            "recycle_file_documents_old_txt",
            "recycle_file",
            "Move Old.txt to Recycle Bin",
            "path=C:\\Users\\Devansh\\Documents\\Old.txt;pre=digest",
            path=Path("C:/Users/Devansh/Documents/Old.txt"),
        )
        match_device.return_value = action
        authorize.return_value = {
            "ok": True,
            "command_id": "command",
            "device_id": "device",
            "permission_scope": "recycle_file",
            "signature_verified": True,
            "nonce_claimed": True,
        }
        execute.return_value = {
            "ok": True,
            "message": "Moved Old.txt to the Windows Recycle Bin.",
            "verification": "Original path absent.",
            "recycled": True,
        }

        result, state = _execute_approved_supported(
            {
                "task_id": "task",
                "task_type": "computer_operation",
                "objective": "recycle file Old.txt from Documents",
            }
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertTrue(result["device_action"]["command_fabric"]["signature_verified"])
        authorize.assert_called_once_with(action)
        execute.assert_called_once_with(action)

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.update_task_state")
    @patch("auris.runtime.save_task")
    @patch("auris.runtime._execute_supported")
    @patch("auris.runtime.get_control_state", return_value={"stopped": False})
    def test_private_command_does_not_persist_task_or_result(
        self, control, execute, save_task, update_task, record_event
    ):
        execute.return_value = (
            {"message": "Private answer", "verification": "Private verification"},
            TaskState.COMPLETED,
        )

        result = process_command("private question", CommandContext(private=True, mode="private"))

        self.assertEqual(result["plan"]["state"], TaskState.COMPLETED.value)
        save_task.assert_not_called()
        update_task.assert_not_called()
        finished = [call for call in record_event.call_args_list if call.args[0] == "task.finished"][0]
        self.assertEqual(finished.args[1]["verification"], "[private result]")

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.create_approval")
    @patch("auris.runtime.save_task")
    @patch("auris.runtime.get_control_state", return_value={"stopped": False})
    def test_private_sensitive_action_does_not_persist_approval(
        self, control, save_task, create_approval, record_event
    ):
        result = process_command(
            "send email to person@example.com subject Update saying Private body.",
            CommandContext(private=True, mode="private"),
        )

        self.assertEqual(result["plan"]["state"], TaskState.FAILED.value)
        save_task.assert_not_called()
        create_approval.assert_not_called()

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.save_task")
    @patch("auris.runtime.set_control_state")
    def test_private_emergency_control_changes_state_without_task_persistence(
        self, set_control, save_task, _record_event
    ):
        set_control.return_value = {"stopped": True, "reason": "private test"}

        result = process_command("AURIS, stop", CommandContext(private=True, mode="private"))

        set_control.assert_called_once()
        save_task.assert_not_called()
        self.assertEqual(result["plan"]["state"], TaskState.COMPLETED.value)
        self.assertEqual(result["result"]["verification_report"]["status"], "verified")

    @patch("auris.runtime.execute_communication_request")
    def test_read_only_communications_result_completes(self, execute):
        execute.return_value = {
            "ok": True,
            "message": "Found one message.",
            "verification": "Read only.",
            "items": [{"subject": "Update"}],
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "communications"},
            "search my email for update",
            None,
            True,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["communications_action"]["items"][0]["subject"], "Update")

    @patch("auris.runtime.execute_communication_request")
    @patch("auris.runtime.match_communication_command")
    def test_approved_call_reresolves_exact_request_and_never_claims_unstarted_call(
        self, match, execute
    ):
        request = CommunicationRequest("start_call", channel="whatsapp", contact="MOM")
        match.return_value = request
        execute.return_value = {
            "ok": False,
            "error": "WhatsApp Desktop is not linked.",
            "verification": "Confirmed: no WhatsApp call was started.",
            "call_started": False,
        }

        result, state = _execute_approved_supported(
            {
                "task_id": "task",
                "task_type": "communications",
                "objective": "make a WhatsApp audio call to MOM",
            }
        )

        self.assertEqual(state, TaskState.FAILED)
        self.assertFalse(result["communications_action"]["call_started"])
        execute.assert_called_once_with(request)

    @patch("auris.runtime.execute_device_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.match_device_commands", return_value=[object()])
    def test_verified_device_action_completes(self, _match, authorize, execute):
        authorize.return_value = {
            "ok": True,
            "command_id": "command",
            "device_id": "device",
            "permission_scope": "launch_app",
            "signature_verified": True,
            "nonce_claimed": True,
        }
        execute.return_value = {
            "ok": True,
            "message": "Opened.",
            "verification": "Confirmed running.",
        }

        _, state = _execute_supported(
            {"task_id": "task", "task_type": "computer_operation"},
            "open Notepad",
            None,
            True,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)

    @patch("auris.runtime.execute_device_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.match_device_commands", return_value=[object()])
    def test_rejected_device_envelope_blocks_windows_execution(self, _match, authorize, execute):
        authorize.return_value = {"ok": False, "error": "Signature invalid."}

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "computer_operation"},
            "open Notepad",
            None,
            True,
            "command",
            "conversation",
        )

        execute.assert_not_called()
        self.assertEqual(state, TaskState.BLOCKED)
        self.assertIn("did not begin", result["verification"])

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.execute_device_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.match_device_commands")
    def test_compound_device_sequence_executes_and_verifies_in_order(
        self, match, authorize, execute, _record_event
    ):
        first = DeviceAction("open_spotify", "launch_app", "Open Spotify", "Spotify")
        second = DeviceAction("play_spotify", "app_media", "Play Spotify", "Spotify")
        match.return_value = [first, second]
        authorize.side_effect = [
            {"ok": True, "command_id": "one", "permission_scope": "launch_app"},
            {"ok": True, "command_id": "two", "permission_scope": "app_media"},
        ]
        execute.side_effect = [
            {"ok": True, "message": "Spotify opened.", "verification": "Process observed."},
            {"ok": True, "message": "Playback requested.", "verification": "Media key emitted."},
        ]

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "computer_operation"},
            "open Spotify and play music",
            None,
            False,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(len(result["device_actions"]), 2)
        self.assertIn("all 2", result["verification"])
        self.assertEqual(execute.call_args_list[0].args[0], first)
        self.assertEqual(execute.call_args_list[1].args[0], second)

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.execute_device_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.match_device_commands")
    def test_compound_device_sequence_stops_after_unverified_step(
        self, match, authorize, execute, _record_event
    ):
        actions = [
            DeviceAction("open_spotify", "launch_app", "Open Spotify", "Spotify"),
            DeviceAction("play_spotify", "app_media", "Play Spotify", "Spotify"),
            DeviceAction("maximize_spotify", "maximize_app", "Maximize Spotify", "Spotify"),
        ]
        match.return_value = actions
        authorize.return_value = {"ok": True, "command_id": "one", "permission_scope": "test"}
        execute.side_effect = [
            {"ok": True, "message": "Opened.", "verification": "Observed."},
            {"ok": False, "error": "Playback unavailable.", "verification": "No media session."},
        ]

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "computer_operation"},
            "open Spotify and play music then maximize it",
            None,
            False,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.PARTIALLY_COMPLETED)
        self.assertEqual(len(result["device_actions"]), 2)
        self.assertEqual(execute.call_count, 2)

    @patch("auris.runtime.run_research")
    def test_research_without_inline_citations_is_partial(self, research):
        research.return_value = {
            "ok": True,
            "message": "Answer without citations.",
            "verification": "Partial.",
            "citations_present": False,
        }

        _, state = _execute_supported(
            {"task_id": "task", "task_type": "research"},
            "research topic",
            None,
            True,
            "research",
            "conversation",
        )

        self.assertEqual(state, TaskState.PARTIALLY_COMPLETED)

    @patch("auris.runtime.record_event")
    @patch("auris.runtime.execute_work_product")
    @patch("auris.runtime.register_managed_project", return_value={"project_id": "work-demo"})
    @patch("auris.runtime.ensure_conversation")
    def test_verified_work_product_returns_artifact_evidence(self, _conversation, _register, execute, record_event):
        execute.return_value = {
            "ok": True,
            "complete": True,
            "message": "Created project.",
            "verification": "Static checks passed; code not executed.",
            "artifact": {
                "kind": "code_project",
                "path": "C:/AURIS Work/Projects/demo",
                "manifest_sha256": "abc",
                "generated_code_executed": False,
            },
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "work_product"},
            "scaffold a Python project called Demo",
            None,
            False,
            "coding",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["artifact_action"]["artifact"]["manifest_sha256"], "abc")
        self.assertEqual(record_event.call_args.args[0], "artifact.generated")

    def test_logic_brief_automatically_delegates_created_project_to_codex(self):
        brief = "build a Python app called Budget that tracks expenses and exports CSV"
        with (
            patch("auris.runtime.record_event"),
            patch("auris.runtime.ensure_conversation"),
            patch("auris.runtime.execute_work_product", return_value={"ok": True, "artifact": {"path": "C:/demo", "name": "Budget"}}),
            patch("auris.runtime.register_managed_project", return_value={"project_id": "work-budget", "root_path": "C:/demo", "name": "Budget"}),
            patch("auris.runtime.codex_cli_status", return_value={"ready": True}),
            patch("auris.runtime.prepare_codex_workspace_change", return_value={"ok": True, "operation": "prepare_codex_workspace_change", "proposal": {"proposal_id": "proposal"}, "message": "Ready", "verification": "Static checks passed"}) as prepare,
        ):
            result, state = _execute_supported({"task_id": "task", "task_type": "work_product"}, brief, "auris-one", False, "coding", "conversation")
        self.assertEqual(state, TaskState.AWAITING_APPROVAL)
        self.assertIn("tracks expenses and exports CSV", prepare.call_args.args[0])
        self.assertEqual(result["coding_action"]["generated_project_id"], "work-budget")

    def test_background_coding_returns_running_without_blocking_command_handler(self):
        with (
            patch("auris.runtime.get_control_state", return_value={"stopped": False}),
            patch("auris.runtime.ensure_conversation"), patch("auris.runtime.append_message"),
            patch("auris.runtime.save_task"), patch("auris.runtime.prepare_workflow"),
            patch("auris.runtime.update_task_state"), patch("auris.runtime.update_workflow_state"),
            patch("auris.runtime.record_event"), patch("auris.runtime.get_workflow_run", return_value=None),
            patch("auris.runtime.codex_cli_status", return_value={"ready": True}),
            patch("auris.runtime.get_conversation", return_value={"project_id": "work-demo"}),
            patch("auris.runtime._CODEX_MISSION_SLOT") as slot,
            patch("auris.runtime.threading.Thread") as worker,
            patch("auris.runtime.execute_workflow") as execute,
        ):
            slot.acquire.return_value = True
            response = process_command("Use Codex to add CSV export in this project", CommandContext(project_id=None, conversation_id="auris-background-voice"))
        self.assertEqual(response["plan"]["state"], "running")
        self.assertTrue(response["result"]["background"])
        worker.return_value.start.assert_called_once()
        self.assertEqual(worker.call_args.kwargs["args"][2], "work-demo")
        execute.assert_not_called()

    def test_generated_project_approval_uses_generated_root_not_original_context(self):
        with (
            patch("auris.runtime.get_project", return_value={"root_path": "C:/demo", "name": "Demo"}) as project,
            patch("auris.runtime.is_trusted_coding_root", return_value=True),
            patch("auris.runtime.apply_codex_workspace_change", return_value={"ok": True, "message": "Applied"}) as apply,
        ):
            result, state = _execute_approved_supported({"task_type": "work_product", "project_id": "auris-one", "result": {"coding_action": {"operation": "prepare_codex_workspace_change", "generated_project_id": "work-demo", "proposal": {"proposal_id": "proposal"}}}})
        self.assertEqual(state, TaskState.COMPLETED)
        project.assert_called_once_with("work-demo")
        self.assertEqual(apply.call_args.kwargs["root"], Path("C:/demo"))

    @patch("auris.runtime.run_research")
    def test_research_completes_only_when_definition_of_done_is_met(self, research):
        research.return_value = {
            "ok": True,
            "message": "Evidence-backed answer [S1].",
            "verification": "Definition of done met.",
            "citations_present": True,
            "definition_of_done_met": True,
        }

        _, state = _execute_supported(
            {"task_id": "task", "task_type": "research"},
            "research deeply topic",
            None,
            True,
            "research",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)

    @patch("auris.runtime.build_daily_brief")
    def test_daily_brief_reports_unloaded_external_context(self, build_brief):
        build_brief.return_value = {
            "primary_objective": "Validate the current build",
            "priorities": [{"level": "P1", "title": "Run verification"}],
            "suggested_first_action": "Run verification.",
            "mailbox_loaded": False,
            "external_calendar_loaded": False,
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "daily_brief"},
            "prepare my daily briefing",
            None,
            True,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertFalse(result["daily_brief"]["mailbox_loaded"])
        self.assertIn("not silently loaded", result["verification"])

    @patch("auris.runtime.execute_coding_command")
    @patch("auris.runtime.get_project")
    def test_project_analysis_uses_selected_registered_root(self, get_project, execute):
        get_project.return_value = {
            "project_id": "infraguard-ai",
            "name": "InfraGuard AI",
            "root_path": "C:\\Projects\\InfraGuard",
        }
        execute.return_value = {
            "ok": True,
            "message": "Project analysed.",
            "verification": "Read-only snapshot verified.",
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "coding"},
            "AURIS, analyse this project",
            "infraguard-ai",
            False,
            "coding",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["coding_action"]["message"], "Project analysed.")
        self.assertEqual(execute.call_args.kwargs["project_name"], "InfraGuard AI")
        self.assertFalse(execute.call_args.kwargs["trusted_execution"])

    @patch("auris.runtime.execute_coding_command")
    @patch("auris.runtime.get_project")
    def test_verified_repair_proposal_returns_dynamic_approval_state(self, get_project, execute):
        get_project.return_value = {
            "project_id": "auris-one",
            "name": "AURIS One",
            "root_path": str(Path(__file__).resolve().parents[1]),
        }
        execute.return_value = {
            "ok": True,
            "operation": "prepare_repair",
            "message": "Verified proposal ready.",
            "verification": "Isolated tests passed; source unchanged.",
            "approval_required": True,
            "proposal": {"proposal_id": "proposal-id"},
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "coding"},
            "AURIS, fix this failing test",
            "auris-one",
            False,
            "coding",
            "conversation",
        )

        self.assertEqual(state, TaskState.AWAITING_APPROVAL)
        self.assertEqual(result["coding_action"]["proposal"]["proposal_id"], "proposal-id")
        self.assertTrue(execute.call_args.kwargs["trusted_execution"])
        self.assertEqual(execute.call_args.kwargs["command"], "AURIS, fix this failing test")

    @patch("auris.runtime.execute_coding_command")
    @patch("auris.runtime.get_project")
    def test_codex_workspace_mission_returns_signed_approval_state(self, get_project, execute):
        get_project.return_value = {
            "project_id": "auris-one",
            "name": "AURIS One",
            "root_path": str(Path(__file__).resolve().parents[1]),
        }
        execute.return_value = {
            "ok": True,
            "operation": "prepare_codex_workspace_change",
            "message": "Codex proposal ready.",
            "verification": "Isolated checks passed; source unchanged.",
            "approval_required": True,
            "proposal": {"proposal_id": "codex-proposal-id", "engine": "codex_cli"},
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "coding"},
            "Use Codex to implement a status endpoint in this project",
            "auris-one",
            False,
            "coding",
            "conversation",
        )

        self.assertEqual(state, TaskState.AWAITING_APPROVAL)
        self.assertEqual(result["coding_action"]["proposal"]["proposal_id"], "codex-proposal-id")
        self.assertTrue(execute.call_args.kwargs["trusted_execution"])
        self.assertEqual(execute.call_args.args[0], "codex_workspace")

    @patch("auris.runtime.execute_coding_command")
    @patch("auris.runtime.get_project")
    def test_private_repair_stops_before_tests_model_or_proposal(self, get_project, execute):
        get_project.return_value = {
            "project_id": "auris-one",
            "name": "AURIS One",
            "root_path": str(Path(__file__).resolve().parents[1]),
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "coding"},
            "AURIS, fix this failing test",
            "auris-one",
            True,
            "private",
            "conversation",
        )

        self.assertEqual(state, TaskState.FAILED)
        self.assertIn("no test process", result["verification"].lower())
        execute.assert_not_called()

    @patch("auris.runtime.apply_test_repair")
    @patch("auris.runtime.get_project")
    def test_approved_repair_applies_only_bound_proposal_and_reports_verification(
        self, get_project, apply_repair
    ):
        project_root = Path(__file__).resolve().parents[1]
        get_project.return_value = {
            "project_id": "auris-one",
            "name": "AURIS One",
            "root_path": str(project_root),
        }
        apply_repair.return_value = {
            "ok": True,
            "operation": "apply_repair",
            "message": "Applied and verified.",
            "verification": "Signed diff, hashes, targeted tests, and complete tests passed.",
            "proposal_id": "proposal-id",
            "rolled_back": False,
        }
        task = {
            "task_id": "task",
            "task_type": "coding",
            "project_id": "auris-one",
            "result": {
                "coding_action": {
                    "operation": "prepare_repair",
                    "proposal": {"proposal_id": "proposal-id"},
                }
            },
        }

        result, state = _execute_approved_supported(task)

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["coding_action"]["proposal_id"], "proposal-id")
        apply_repair.assert_called_once_with(
            "proposal-id", root=project_root, trusted_execution=True
        )

    @patch("auris.runtime.apply_codex_workspace_change")
    @patch("auris.runtime.get_project")
    def test_approved_codex_change_applies_only_bound_proposal(self, get_project, apply_change):
        project_root = Path(__file__).resolve().parents[1]
        get_project.return_value = {
            "project_id": "auris-one",
            "name": "AURIS One",
            "root_path": str(project_root),
        }
        apply_change.return_value = {
            "ok": True,
            "operation": "apply_codex_workspace_change",
            "message": "Applied and verified.",
            "verification": "Signed diff, source hashes, static checks, and tests passed.",
            "proposal_id": "codex-proposal-id",
            "rolled_back": False,
        }
        task = {
            "task_id": "task",
            "task_type": "coding",
            "project_id": "auris-one",
            "result": {
                "coding_action": {
                    "operation": "prepare_codex_workspace_change",
                    "proposal": {"proposal_id": "codex-proposal-id"},
                }
            },
        }

        result, state = _execute_approved_supported(task)

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["coding_action"]["proposal_id"], "codex-proposal-id")
        apply_change.assert_called_once_with(
            "codex-proposal-id", root=project_root, trusted_execution=True
        )

    @patch("auris.runtime.get_project", return_value={"project_id": "career", "root_path": None})
    def test_project_analysis_requires_registered_root(self, _get_project):
        result, state = _execute_supported(
            {"task_id": "task", "task_type": "coding"},
            "AURIS, analyse this project",
            "career",
            False,
            "coding",
            "conversation",
        )

        self.assertEqual(state, TaskState.FAILED)
        self.assertIn("registered local root", result["message"])

    @patch("auris.runtime.execute_device_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.resolve_project_open_action")
    @patch("auris.runtime.match_project_open_command")
    def test_project_open_uses_signed_fabric_and_observed_result(
        self, match, resolve, authorize, execute
    ):
        request = ProjectOpenRequest(None, True)
        action = DeviceAction(
            "open_project_auris_one",
            "open_folder",
            "Open AURIS One project",
            "C:\\AURIS",
            path=Path("C:\\AURIS"),
            source="registered_project",
        )
        match.return_value = request
        resolve.return_value = (
            action,
            {"project_id": "auris-one", "name": "AURIS One"},
            None,
        )
        authorize.return_value = {
            "ok": True,
            "command_id": "command",
            "device_id": "device",
            "permission_scope": "open_folder",
            "signature_verified": True,
            "nonce_claimed": True,
        }
        execute.return_value = {
            "ok": True,
            "message": "AURIS One opened in File Explorer.",
            "verification": "Exact registered root observed.",
            "application": "File Explorer",
            "observed_path": "C:\\AURIS",
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "project_operation"},
            "AURIS, open this project",
            "auris-one",
            False,
            "command",
            "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertTrue(result["project_action"]["command_fabric"]["signature_verified"])
        self.assertEqual(result["project_action"]["observed_path"], "C:\\AURIS")
        authorize.assert_called_once_with(action)

    @patch("auris.runtime.execute_browser_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.build_browser_device_action")
    @patch("auris.runtime.match_browser_command")
    def test_browser_navigation_uses_signed_fabric_and_page_verification(
        self, match, build, authorize, execute
    ):
        request = BrowserAction("navigate", "Open example.com", "https://example.com")
        device_action = DeviceAction("browser_navigate_test", "browser_navigate", "Open page", "name=example.com;value=none")
        match.return_value = request
        build.return_value = device_action
        authorize.return_value = {"ok": True, "signature_verified": True, "nonce_claimed": True, "permission_scope": "browser_navigate"}
        execute.return_value = {"ok": True, "message": "Opened.", "verification": "HTTP 200 and title observed."}

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "browser_workflow"},
            "AURIS, open example.com", "auris-one", False, "command", "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertTrue(result["browser_action"]["command_fabric"]["signature_verified"])
        authorize.assert_called_once_with(device_action)

    @patch("auris.runtime.execute_browser_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.build_browser_device_action")
    @patch("auris.runtime.match_browser_command")
    def test_approved_browser_fill_reresolves_and_uses_signed_once_scope(
        self, match, build, authorize, execute
    ):
        request = BrowserAction("fill", "Fill Note", accessible_name="Note", value="Approved")
        device_action = DeviceAction("browser_fill_test", "browser_fill", "Fill Note", "name=Note;value=digest")
        match.return_value = request
        build.return_value = device_action
        authorize.return_value = {"ok": True, "signature_verified": True, "nonce_claimed": True, "permission_scope": "browser_fill"}
        execute.return_value = {"ok": True, "message": "Filled.", "verification": "Exact value read back."}

        result, state = _execute_approved_supported({
            "task_id": "task", "task_type": "browser_workflow",
            "objective": 'fill "Note" with "Approved" in the browser',
        })

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertTrue(result["browser_action"]["command_fabric"]["nonce_claimed"])
        execute.assert_called_once_with(request)

    @patch("auris.runtime.execute_browser_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.build_browser_device_action")
    @patch("auris.runtime.match_browser_command")
    def test_approved_browser_mission_reresolves_exact_steps_and_signed_scope(
        self, match, build, authorize, execute
    ):
        request = BrowserAction("workflow", "Mission", steps=(
            BrowserStep("navigate", url="https://example.com/form"),
            BrowserStep("fill", accessible_name="Note", value="Approved"),
            BrowserStep("click", accessible_name="Preview"),
        ))
        device_action = DeviceAction("browser_workflow_test", "browser_workflow", "Mission", "steps=3;digest=abc")
        match.return_value = request
        build.return_value = device_action
        authorize.return_value = {"ok": True, "signature_verified": True, "nonce_claimed": True, "permission_scope": "browser_workflow"}
        execute.return_value = {"ok": True, "message": "Completed.", "verification": "All checkpoints observed.", "completed_steps": 3}

        result, state = _execute_approved_supported({
            "task_id": "task", "task_type": "browser_workflow",
            "objective": 'run browser mission open "https://example.com/form" then fill "Note" with "Approved" then click "Preview"',
        })

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["browser_action"]["completed_steps"], 3)
        self.assertEqual(result["browser_action"]["command_fabric"]["permission_scope"], "browser_workflow")
        execute.assert_called_once_with(request)

    @patch("auris.runtime.execute_browser_action")
    def test_private_browser_session_does_not_start_worker(self, execute):
        result, state = _execute_supported(
            {"task_id": "task", "task_type": "browser_workflow"},
            "AURIS, inspect the current browser page", "auris-one", True, "private", "conversation",
        )

        self.assertEqual(state, TaskState.FAILED)
        self.assertIn("Private mode", result["message"])
        execute.assert_not_called()

    @patch("auris.runtime.application_state_dashboard")
    def test_application_state_show_is_read_only(self, dashboard):
        dashboard.return_value = {
            "active": {
                "status": "resumable",
                "checkpoint": {"completed_steps": 2, "total_steps": 4},
            },
            "states": [],
            "policy": {},
        }

        result, state = _execute_supported(
            {"task_id": "task", "task_type": "application_state"},
            "show active browser mission", "auris-one", False, "command", "conversation",
        )

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertIn("2 of 4", result["message"])
        dashboard.assert_called_once_with("auris-one")

    @patch("auris.runtime.set_application_state_status")
    @patch("auris.runtime.record_browser_application_state")
    @patch("auris.runtime.execute_browser_action")
    @patch("auris.runtime.authorize_local_device_action")
    @patch("auris.runtime.resolve_browser_continuation")
    def test_approved_continuation_revalidates_exact_state_and_supersedes_it(
        self, resolve, authorize, execute, record_state, set_status
    ):
        request = BrowserAction("workflow", "Mission", steps=(
            BrowserStep("navigate", url="https://example.com/form"),
            BrowserStep("fill", accessible_name="Note", value="Approved"),
            BrowserStep("click", accessible_name="Preview"),
        ))
        source = {
            "task_id": "source-task",
            "task_type": "browser_workflow",
            "objective": 'run browser mission open "https://example.com/form" then fill "Note" with "Approved" then click "Preview"',
        }
        resolve.return_value = ({"state_id": "state-1", "status": "resumable"}, source, None)
        authorize.return_value = {
            "ok": True, "signature_verified": True, "nonce_claimed": True,
            "permission_scope": "browser_workflow",
        }
        execute.return_value = {
            "ok": True, "message": "Completed.", "verification": "All checkpoints observed.",
            "completed_steps": 3,
        }
        record_state.return_value = {"state_id": "state-2", "status": "completed"}

        result, state = _execute_approved_supported({
            "task_id": "continue-task",
            "task_type": "application_state",
            "project_id": "auris-one",
            "result": {"application_state_reference": {
                "state_id": "state-1", "source_task_id": "source-task",
            }},
        })

        self.assertEqual(state, TaskState.COMPLETED)
        self.assertEqual(result["continued_from"]["state_id"], "state-1")
        resolve.assert_called_once_with("auris-one", state_id="state-1")
        execute.assert_called_once()
        record_state.assert_called_once()
        set_status.assert_called_once_with("state-1", "superseded")


if __name__ == "__main__":
    unittest.main()
