import unittest
from unittest.mock import AsyncMock, Mock, patch

import main


class ConfigurationTests(unittest.TestCase):
    def test_validate_configuration_returns_admin_id(self):
        with (
            patch.object(main, "BOT_TOKEN", "telegram-token"),
            patch.object(main, "OPENROUTER_API_KEY", "openrouter-key"),
            patch.object(main, "ADMIN_ID", "12345"),
        ):
            self.assertEqual(main.validate_configuration(), 12345)

    def test_validate_configuration_reports_missing_values(self):
        with (
            patch.object(main, "BOT_TOKEN", ""),
            patch.object(main, "OPENROUTER_API_KEY", "openrouter-key"),
            patch.object(main, "ADMIN_ID", ""),
        ):
            with self.assertRaisesRegex(RuntimeError, "BOT_TOKEN, ADMIN_ID"):
                main.validate_configuration()

    def test_validate_configuration_rejects_non_numeric_admin_id(self):
        with (
            patch.object(main, "BOT_TOKEN", "telegram-token"),
            patch.object(main, "OPENROUTER_API_KEY", "openrouter-key"),
            patch.object(main, "ADMIN_ID", "not-a-number"),
        ):
            with self.assertRaisesRegex(RuntimeError, "ADMIN_ID must be a positive integer"):
                main.validate_configuration()


class AskAITests(unittest.IsolatedAsyncioTestCase):
    async def test_request_includes_current_message_once(self):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "Hello there"}}]
        }
        client = Mock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        client.post = AsyncMock(return_value=response)

        with (
            patch.object(main, "OPENROUTER_API_KEY", "test-api-key"),
            patch(
                "main.get_conversation_history",
                new_callable=AsyncMock,
                return_value=[{"role": "user", "content": "previous message"}],
            ),
            patch("main.httpx.AsyncClient", return_value=client),
        ):
            reply = await main.ask_ai(12345, "current message")

        self.assertEqual(reply, "Hello there")
        request = client.post.await_args.kwargs
        self.assertEqual(
            request["headers"]["Authorization"], "Bearer test-api-key"
        )
        messages = request["json"]["messages"]
        current_messages = [
            message for message in messages if message["content"] == "current message"
        ]
        self.assertEqual(len(current_messages), 1)


class HandlerAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_button_handler_rejects_non_admin(self):
        query = Mock()
        query.from_user.id = 67890
        query.answer = AsyncMock()
        update = Mock(callback_query=query)

        with patch.object(main, "ADMIN_ID", "12345"):
            await main.button_handler(update, Mock())

        query.answer.assert_awaited_once_with(
            "You are not authorized to use this bot.", show_alert=True
        )


if __name__ == "__main__":
    unittest.main()
