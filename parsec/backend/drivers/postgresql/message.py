from parsec.backend.message import BaseMessageComponent


class PGMessageComponent(BaseMessageComponent):
    def __init__(self, dbh, *args):
        super().__init__(*args)
        self.dbh = dbh

    async def perform_message_new(self, sender_device_id, recipient_user_id, body):
        async with self.dbh.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (sender_device_id, recipient_user_id, body) VALUES ($1, $2, $3)",
                sender_device_id,
                recipient_user_id,
                body,
            )
        self._signal_message_arrived.send(recipient_user_id)

    async def perform_message_get(self, recipient_user_id, offset):
        async with self.dbh.pool.acquire() as conn:
            return await conn.fetch(
                """
                    SELECT sender_device_id, body FROM messages WHERE recipient_user_id = $1 OFFSET $2
                    """,
                recipient_user_id,
                offset,
            )
