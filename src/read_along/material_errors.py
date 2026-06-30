"""材料库错误类型。"""


class MaterialLibraryError(RuntimeError):
    """材料库操作失败。"""


class InvalidDraftError(MaterialLibraryError):
    """阅读材料 Draft 不合法。"""


class SourceChangedError(MaterialLibraryError):
    """已有来源身份对应的结构化正文发生变化。"""


class MaterialNotFoundError(MaterialLibraryError):
    """指定阅读材料不存在。"""


class AudioGenerationError(MaterialLibraryError):
    """句子音频暂时无法生成或访问。"""


class AudioNotFoundError(MaterialLibraryError):
    """指定句子音频不存在或不属于指定材料。"""


class InvalidProgressError(MaterialLibraryError):
    """阅读进度不合法。"""
