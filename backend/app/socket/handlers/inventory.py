import logging
import traceback
from db.session import AsyncSessionLocal
from app.socket.decorators import socket_event_handler
from app.services.game_service import GameService
from app.services.loot_service import LootService
from app.services.state_service import StateService

logger = logging.getLogger(__name__)

@socket_event_handler
async def handle_take_items(sid, data, sio, connected_users):
    user_info = connected_users.get(sid)
    if not user_info:
        logger.warning(f"[Inventory] No user info found for sid {sid}")
        return

    campaign_id = user_info.get("campaign_id")
    actor_id = data.get("actor_id")
    vessel_id = data.get("vessel_id")
    item_ids = data.get("item_ids", [])
    take_currency = data.get("take_currency", False)

    try:
        async with AsyncSessionLocal() as db:
            result = await LootService.take_items(campaign_id, actor_id, vessel_id, item_ids, take_currency, db)

            if result["success"]:
                # Notify everyone of the game state change if needed, but LootService.take_items
                # didn't explicitly emit the event. We'll emit it here.
                # Actually, `GameService.save_game_state` just saves to DB. We need to emit.
                game_state = await GameService.get_game_state(campaign_id, db)
                await StateService.emit_state_update(campaign_id, game_state, sio)

                # We could also emit a system message depending on whether we want to spam chat
                # Let's emit a subtle message or nothing, the GUI will update.
                return {"success": True}
            else:
                await sio.emit('system_message', {"content": result.get("message", "Error taking items.")}, room=sid)
                return {"success": False, "message": result.get("message")}
    except Exception as e:
        logger.error(f"[Inventory] Error in handle_take_items: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": str(e)}

@socket_event_handler
async def handle_equip_item(sid, data, sio, connected_users):
    user_info = connected_users.get(sid)
    if not user_info:
        logger.warning(f"[Inventory] No user info found for sid {sid}")
        return

    campaign_id = user_info.get("campaign_id")
    actor_id = data.get("actor_id")
    item_id = data.get("item_id")
    is_equip = data.get("is_equip", True) # True to equip, False to unequip
    target_slot = data.get("target_slot")

    try:
        async with AsyncSessionLocal() as db:
            result = await LootService.equip_item(campaign_id, actor_id, item_id, is_equip, db, target_slot=target_slot)

            if result["success"]:
                game_state = await GameService.get_game_state(campaign_id, db)
                await StateService.emit_state_update(campaign_id, game_state, sio)

                # Emit a system message just for flavor ("X equips Y")
                actor = result.get("actor")
                action = "equips" if is_equip else "unequips"
                flavor_msg = f"{actor.name} {action} {item_id.replace('-', ' ').title()}."
                await sio.emit('system_message', {"content": flavor_msg}, room=campaign_id)

                return {"success": True}
            else:
                await sio.emit('system_message', {"content": result.get("message", "Error equipping item.")}, room=sid)
                return {"success": False, "message": result.get("message")}
    except Exception as e:
        logger.error(f"[Inventory] Error in handle_equip_item: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": str(e)}
