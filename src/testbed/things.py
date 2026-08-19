"""内存 CRUD /things 路由。"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/things", tags=["things"])

_things: dict[int, dict] = {}
_next_id: int = 1


def _get_thing_or_404(thing_id: int) -> dict:
    """按 id 取 thing; 不存在则统一抛出 404。"""
    if thing_id not in _things:
        raise HTTPException(status_code=404, detail="Not found")
    return _things[thing_id]


@router.post("", status_code=201)
def create_thing(data: dict) -> dict:
    global _next_id
    thing_id = _next_id
    _next_id += 1
    thing = {"id": thing_id, "content": data.get("content", "")}
    _things[thing_id] = thing
    return thing


@router.get("/{thing_id}")
def get_thing(thing_id: int) -> dict:
    return _get_thing_or_404(thing_id)


@router.put("/{thing_id}")
def update_thing(thing_id: int, data: dict) -> dict:
    thing = _get_thing_or_404(thing_id)
    thing["content"] = data.get("content", "")
    return thing


@router.delete("/{thing_id}", status_code=204)
def delete_thing(thing_id: int) -> None:
    _get_thing_or_404(thing_id)
    del _things[thing_id]
