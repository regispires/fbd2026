"""
Processamento das imagens de banner dos eventos.

O arquivo enviado é convertido para JPEG e reduzido a uma miniatura de
400x225 (16:9, usada nos cartões da listagem). Os dois arquivos são
guardados no banco, nas colunas ``BYTEA`` ``evento.banner`` e
``evento.banner_thumbnail``, e exibidos no HTML como *data URL* em base64
(``para_data_url``): não há arquivos em disco nem rota de imagens.

O módulo não depende do NiceGUI nem do banco, então também é usado para
gerar as imagens do script de população (``scripts/03_banners.sql``).
"""

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.exceptions import ImagemInvalida

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


def _jpeg(imagem: Image.Image) -> bytes:
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=QUALIDADE_JPEG)
    return saida.getvalue()


def processar_banner(conteudo: bytes) -> tuple[bytes, bytes]:
    """
    Converte a imagem enviada em ``(banner, banner_thumbnail)``, ambos
    JPEG, prontos para as colunas ``BYTEA`` do evento.

    A miniatura é recortada no centro para preencher exatamente 400x225,
    sem distorcer a imagem. Lança ``ImagemInvalida`` se o arquivo não for
    uma imagem.
    """
    imagem = _abrir_imagem(conteudo)
    thumbnail = ImageOps.fit(imagem, TAMANHO_THUMBNAIL, Image.Resampling.LANCZOS)
    return _jpeg(imagem), _jpeg(thumbnail)


def para_data_url(jpeg: bytes) -> str:
    """
    Data URL (``data:image/jpeg;base64,...``) para exibir os bytes de uma
    imagem JPEG diretamente no ``src`` de um ``<img>``.
    """
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
