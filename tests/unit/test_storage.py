import os
import pytest
import tempfile
from pathlib import Path
from backend.app.storage.local import LocalStorageProvider

@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as td:
        yield LocalStorageProvider(root_dir=td)

@pytest.mark.asyncio
async def test_auto_directory_creation(temp_storage):
    root = temp_storage.root_dir
    assert (root / "videos").exists()
    assert (root / "audio").exists()
    assert (root / "images").exists()
    assert (root / "thumbnails").exists()
    assert (root / "temp").exists()

@pytest.mark.asyncio
async def test_save_and_retrieve(temp_storage):
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("Auvyra test video content data")
        temp_src = f.name
        
    dest_key = "videos/clip1.txt"
    saved_key = await temp_storage.save(temp_src, dest_key)
    assert saved_key == dest_key
    assert await temp_storage.exists(dest_key)
    
    file_path = await temp_storage.get(dest_key)
    assert os.path.exists(file_path)
    with open(file_path, "r") as rf:
        assert rf.read() == "Auvyra test video content data"
        
    # Test delete
    deleted = await temp_storage.delete(dest_key)
    assert deleted is True
    assert not await temp_storage.exists(dest_key)
    
    os.remove(temp_src)

@pytest.mark.asyncio
async def test_path_traversal_prevention(temp_storage):
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("malicious payload")
        temp_src = f.name

    with pytest.raises(ValueError, match="Path traversal detected"):
        await temp_storage.save(temp_src, "../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        await temp_storage.get("../../../secret.key")

    os.remove(temp_src)

