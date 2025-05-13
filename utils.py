import json

from gurux_dlms import GXUInt16     # present in all wheels
from gurux_dlms.enums import ObjectType


# ---------- tiny util ----------
def _class_id(raw):
    """Return the numeric class-ID from either enum, GXUInt16, or int."""
    return int(raw) if isinstance(raw, (int, GXUInt16)) else raw.value


# ---------- save ----------
def save_object_list(client, path=None, obj_limit=None):
    """
    Walk through cli.objects and cache:
      • class-ID
      • class-name
      • version
      • logical-name
      • list of attributes where obj.canRead(idx) == True
    """
    if path is None:
        path = "./objects_cache.json"

    serial = []
    max_obj = obj_limit
    obj_idx = 0
    for o in client.objects:
        if max_obj:
            obj_idx += 1
            if obj_idx > max_obj:
                break
        attrs = []
        try:
            cnt = o.getAttributeCount()
        except AttributeError:
            cnt = 0
        for idx in range(1, cnt + 1):
            try:
                if o.canRead(idx):
                    attrs.append(idx)
            except Exception:
                pass              # some objects lack canRead for high idx

        serial.append({
            "class_id"   : _class_id(o.objectType),
            "class_name"   : class_name(o.objectType),
            "version"    : getattr(o, "version", 0),
            "logicalName": o.logicalName,
            "readable"   : attrs
        })
    path.write_text(json.dumps(serial, indent=2))
    print(f"[DLMS] cached {len(serial)} objects → {path}")


# ---------- load ----------
def load_object_list(client, path=None, obis_filter=None):
    """
    Load cached objects AND stash the readable attribute list into
    obj.__dict__["_cached_readable"] for later use.
    Returns True if cache was loaded, False if file missing.
    """
    if path is None:
        path = "./objects_cache.json"

    if not path.exists():
        return False

    serial = json.loads(path.read_text())
    for item in serial:
        cls_id = item["class_id"]
        ln     = item["logicalName"]
        ver    = item.get("version", 0)
        attrs  = item.get("readable", [])
        obis_found = []
        if obis_filter is not None:
            if ln not in obis_filter:
                if set(obis_found) == set(obis_filter):
                    break
                continue
        else:
            obis_found.append(ln)

        try:
            obj = client.createObject(ObjectType(cls_id))
        except ValueError:
            # unknown class → fallback to Data
            from gurux_dlms.objects import GXDLMSData
            obj = GXDLMSData()

        obj.logicalName = ln
        obj.version     = ver
        obj.__dict__["_cached_readable"] = attrs
        obj.className = item['class_name']
        client.objects.append(obj)

    print(f"[DLMS] loaded {len(serial)} objects from cache")
    return True


def class_name(raw):
    """
    Accepts ObjectType enum OR GXUInt16 OR int
    → returns the textual class name or the numeric ID.
    """
    # already an enum?
    if hasattr(raw, "name"):
        return raw.name
    # wrapper GXUInt16
    if isinstance(raw, GXUInt16):
        v = int(raw)          # unwrap
    else:
        v = int(raw)
    try:
        return ObjectType(v).name
    except ValueError:
        return f"Class-{v}"
