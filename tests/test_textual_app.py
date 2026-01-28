# tests/test_textual_app.py
import pytest
import asyncio
from textual.pilot import Pilot
from modules.textual_app import MicroXTextualApp, CommandInput, KeyHintBar
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_app_initialization():
    app = MicroXTextualApp()
    async with app.run_test() as pilot:
        assert app.query_one(CommandInput)
        assert app.query_one("#main_log")
        assert app.query_one(KeyHintBar)
        assert app.query_one("#interaction_zone").has_class("hidden")

@pytest.mark.asyncio
async def test_command_submission():
    mock_engine = MagicMock()
    mock_engine.main_normal_input_accept_handler_ref = MagicMock()
    
    app = MicroXTextualApp(shell_engine=mock_engine)
    async with app.run_test() as pilot:
        input_widget = app.query_one(CommandInput)
        input_widget.text = "echo hello"
        await pilot.press("enter")
        
        # Check history
        assert app.history == ["echo hello"]
        # Check handler called
        mock_engine.main_normal_input_accept_handler_ref.assert_called_with("echo hello")
        # Check input cleared
        assert input_widget.text == ""

@pytest.mark.asyncio
async def test_history_navigation():
    history = ["cmd1", "cmd2"]
    # App reverses history: ["cmd2", "cmd1"]
    app = MicroXTextualApp(history=history)
    async with app.run_test() as pilot:
        input_widget = app.query_one(CommandInput)
        
        # First UP goes to the end of the reversed list -> "cmd1"
        await pilot.press("up")
        assert input_widget.text == "cmd1"
        
        # Next UP goes to previous index -> "cmd2"
        await pilot.press("up")
        assert input_widget.text == "cmd2"
        
        # Down goes back to "cmd1"
        await pilot.press("down")
        assert input_widget.text == "cmd1"
        
        # Down goes back to empty
        await pilot.press("down")
        assert input_widget.text == ""

@pytest.mark.asyncio
async def test_key_hints_trigger_actions():
    mock_engine = MagicMock()
    mock_engine.handle_built_in_command = AsyncMock()
    
    app = MicroXTextualApp(shell_engine=mock_engine)
    async with app.run_test() as pilot:
        # Test F1 Help
        await pilot.press("f1")
        mock_engine.handle_built_in_command.assert_called_with("/help")
        
        # Test Ctrl+D Docs
        await pilot.press("ctrl+d")
        mock_engine.handle_built_in_command.assert_called_with("/docs")

@pytest.mark.asyncio
async def test_append_output_text():
    app = MicroXTextualApp()
    async with app.run_test() as pilot:
        app.append_output("Hello World", style_class="info")
        # Wait for potential refresh
        await pilot.pause()
        log_widget = app.query_one("#main_log")
        # Textual RichLog content isn't easily assertable as string, 
        # but we can check if it didn't crash and maybe check lines if accessible
        assert log_widget

@pytest.mark.asyncio
async def test_show_confirmation_modal():
    app = MicroXTextualApp()
    async with app.run_test() as pilot:
        # Start modal in background task
        task = asyncio.create_task(app.show_confirmation_modal("ls -la", "/translate list"))
        await pilot.pause()
        
        # Check if interaction zone is visible
        interaction_zone = app.query_one("#interaction_zone")
        assert not interaction_zone.has_class("hidden")
        assert app.query_one("InlineConfirmation")
        
        # Simulate selection (e.g. Run)
        await pilot.press("enter")
        
        result = await task
        assert result == "execute"
        
        # Check if returned to input
        assert interaction_zone.has_class("hidden")

@pytest.mark.asyncio
async def test_show_safety_modal():
    app = MicroXTextualApp()
    async with app.run_test() as pilot:
        task = asyncio.create_task(app.show_safety_modal("rm -rf /"))
        await pilot.pause()
        
        assert app.query_one("InlineSafetyWarning")
        
        # Navigate to "Proceed" (Right -> Enter)
        await pilot.press("right")
        await pilot.press("enter")
        
        result = await task
        assert result is True

