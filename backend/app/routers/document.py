"""文档上传接口"""
from pathlib import Path
from app.rag.store import rebuild_store
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.config import UPLOAD_DIR, SAMPLES_DIR

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_SUFFIX = ".txt"   # 目前只放行 txt，PDF 以后再说


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """接收上传的 txt 文件，存到 UPLOAD_DIR"""
    # ① 校验后缀
    if not file.filename.endswith(ALLOWED_SUFFIX):
        raise HTTPException(status_code=400, detail=f"只支持 {ALLOWED_SUFFIX} 文件")

    # ② 只取文件名，丢掉路径部分（安全处理，见下面讲解⑤）
    filename = Path(file.filename).name

    # ③ 目录不存在就创建
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # ④ 读取内容并写盘
    content = await file.read()
    dest = UPLOAD_DIR / filename
    dest.write_bytes(content)

    # ⑤ 重建知识库（全量：samples + uploads）
    vectorstore = rebuild_store()
    chunks = vectorstore.index.ntotal

    return {
        "filename": filename,
        "size": len(content),
        "chunks": chunks,
        "message": f"上传成功，知识库已重建，共 {chunks} 块",
    }

@router.get("")
def list_documents():
    """列出知识库里的所有 txt 文件名（samples + uploads）"""
    files = sorted(p.name for p in SAMPLES_DIR.glob("*.txt"))
    files += sorted(p.name for p in UPLOAD_DIR.glob("*.txt"))
    return {"files": files}
