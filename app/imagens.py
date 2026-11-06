"""
Armazenamento das imagens de banner dos eventos.

O arquivo enviado é convertido para JPEG e salvo na pasta ``upload`` da
raiz do projeto, junto de uma miniatura de 400x225 (16:9, usada nos
cartões da listagem). Os arquivos são servidos publicamente pela rota
estática ``/imagens`` (registrada em ``app.main``) e o banco guarda apenas
as URLs:

- ``upload/banner/{uuid}.jpg`` -> ``/imagens/banner/{uuid}.jpg``
- ``upload/banner/{uuid}_thumbnail.jpg`` -> ``/imagens/banner/{uuid}_thumbnail.jpg``

O módulo não depende do NiceGUI nem do banco, então também é usado para
gerar as imagens do script de população.
"""

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.exceptions import ImagemInvalida

# raiz do projeto (independe do diretório de onde a aplicação é executada)
PASTA_UPLOAD = Path(__file__).resolve().parent.parent / "upload"
PASTA_BANNER = PASTA_UPLOAD / "banner"
URL_UPLOAD = "/imagens"
URL_BANNER = f"{URL_UPLOAD}/banner"

TAMANHO_THUMBNAIL = (400, 225)
QUALIDADE_JPEG = 85


def _abrir_imagem(conteudo: bytes) -> Image.Image:
    """
    Decodifica os bytes enviados, lançando ``ImagemInvalida`` quando não
    são uma imagem que o Pillow consiga ler (inclui imagens gigantes que
    disparam a proteção contra *decompression bomb*).
    """
    try:
        imagem = Image.open(io.BytesIO(conteudo))
        imagem.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ImagemInvalida from e
    # fotos de celular guardam a rotação no EXIF; aplicá-la evita banners deitados
    imagem = ImageOps.exif_transpose(imagem)
    # JPEG não tem transparência nem paleta
    return imagem.convert("RGB")


def salvar_banner(conteudo: bytes) -> tuple[str, str]:
    """
    Salva o banner e gera a miniatura, devolvendo as URLs públicas
    ``(banner, banner_thumbnail)``.

    A miniatura é recortada no centro para preencher exatamente 400x225,
    sem distorcer a imagem.
    """
    imagem = _abrir_imagem(conteudo)
    thumbnail = ImageOps.fit(imagem, TAMANHO_THUMBNAIL, Image.Resampling.LANCZOS)

    nome = uuid.uuid4()
    PASTA_BANNER.mkdir(parents=True, exist_ok=True)
    imagem.save(PASTA_BANNER / f"{nome}.jpg", "JPEG", quality=QUALIDADE_JPEG)
    thumbnail.save(
        PASTA_BANNER / f"{nome}_thumbnail.jpg", "JPEG", quality=QUALIDADE_JPEG
    )
    return f"{URL_BANNER}/{nome}.jpg", f"{URL_BANNER}/{nome}_thumbnail.jpg"


def remover_banner(*urls: str | None) -> None:
    """
    Remove os arquivos locais das URLs informadas. URLs externas (ou que
    não apontem para um arquivo da pasta de banners) são ignoradas, então
    é seguro chamar com qualquer valor das colunas ``banner``.
    """
    for url in urls:
        if not url or not url.startswith(f"{URL_BANNER}/"):
            continue
        arquivo = (PASTA_BANNER / url.removeprefix(f"{URL_BANNER}/")).resolve()
        # impede que um valor como "../../x" apague algo fora da pasta
        if arquivo.parent == PASTA_BANNER.resolve():
            arquivo.unlink(missing_ok=True)
