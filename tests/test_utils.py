import asyncio
import unittest
from unittest.mock import MagicMock

from ampo.utils import period_check_future


class Utils(unittest.IsolatedAsyncioTestCase):

    async def test_period_check_future(self):
        """
        Base usage
        """
        async def check(ft: asyncio.Future):
            await asyncio.sleep(0.1)
            ft.set_result(True)
        logger = MagicMock()
        ft = asyncio.Future()

        # Process
        asyncio.create_task(check(ft))
        await period_check_future(
            aws=ft,
            logger=logger,
            msg="test",
            period=0.06,
        )
        self.assertEqual(logger.info.call_count, 1)

        # Check default value
        ft = asyncio.Future()
        asyncio.create_task(check(ft))
        await period_check_future(aws=ft)
