BEGIN;

-- Criando tipos 'enum' para definir um conjunto específico de valores aceitos
-- Nota: enums tem a desvantagem de não poderem ser editadas, então atualizar algum novo
--       valor exige mudar a coluna para um tipo genérico, criar uma nova enum com os
--       valores suportados e então converter para essa nova enum

CREATE TYPE papel_usuario AS ENUM ('administrador', 'associado');

CREATE TYPE status_inscricao AS ENUM ('confirmada', 'pendente', 'cancelada');

-- M = masculino, F = feminino, O = outros
CREATE TYPE sexo_usuario AS ENUM ('M', 'F', 'O');



CREATE TABLE IF NOT EXISTS usuario (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    cpf CHAR(11) UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    papel PAPEL_USUARIO NOT NULL DEFAULT 'associado',
    sexo SEXO_USUARIO NOT NULL,
    data_nascimento DATE NOT NULL
    -- idade não pode ser uma coluna virtual porque depende da data atual (função mutável)
    -- por isso ela é adicionada em uma view
);

CREATE OR REPLACE VIEW usuario_com_idade AS (
    SELECT id, nome, cpf, email, papel, sexo, data_nascimento,
           EXTRACT(YEARS FROM AGE(data_nascimento)) as idade
    FROM usuario
);

CREATE TABLE IF NOT EXISTS evento (
    id SERIAL PRIMARY KEY,
    nome TEXT UNIQUE NOT NULL,
    descricao TEXT,
    data_hora_inicio TIMESTAMPTZ NOT NULL,
    data_hora_fim TIMESTAMPTZ NOT NULL,
    -- criando uma restrição de valores com CHECK
    classificacao_indicativa INTEGER CHECK(classificacao_indicativa IN (null,10,12,14,16,18)),
    vagas INTEGER NOT NULL,
    localizacao POINT, -- utilizando o tipo de dados padrão do postgres
    -- URLs das imagens do evento: o banner em tamanho cheio (página de detalhes)
    -- e uma versão reduzida para as listagens
    banner TEXT,
    banner_thumbnail TEXT,
    valor FLOAT NOT NULL
);

CREATE TABLE IF NOT EXISTS atividade (
    -- gerado pelo banco; único na tabela inteira, mas a PK é composta com o
    -- evento para que presença e ministrantes referenciem (id, id_evento) e
    -- não possam apontar para uma atividade de outro evento
    id SERIAL UNIQUE NOT NULL,
    id_evento INTEGER REFERENCES evento(id) NOT NULL,
    nome TEXT NOT NULL,
    descricao TEXT,
    sala TEXT NOT NULL, 
    vagas INTEGER NOT NULL,
    data_hora_inicio TIMESTAMPTZ NOT NULL,
    data_hora_fim TIMESTAMPTZ NOT NULL,

    PRIMARY KEY (id,id_evento)
);

CREATE TABLE IF NOT EXISTS inscricao_evento (
    id_usuario INTEGER REFERENCES usuario(id) NOT NULL,
    id_evento INTEGER REFERENCES evento(id) NOT NULL,
    data_inscricao TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status STATUS_INSCRICAO NOT NULL DEFAULT 'pendente',
    comentario_administrador TEXT,
    comprovante_usuario BYTEA,
    valor FLOAT,
    meia BOOLEAN NOT NULL DEFAULT FALSE,

    PRIMARY KEY (id_usuario,id_evento)
);

CREATE TABLE IF NOT EXISTS presenca_atividade(
    id_usuario INTEGER NOT NULL,
    id_evento INTEGER NOT NULL,
    id_atividade INTEGER NOT NULL,

    PRIMARY KEY (id_usuario,id_evento,id_atividade),

    FOREIGN KEY (id_atividade,id_evento) REFERENCES atividade(id,id_evento),

    -- utilizando uma chave estrangeira composta para referenciar apenas
    -- usuários que participam de um evento como participantes
    FOREIGN KEY (id_usuario,id_evento) REFERENCES inscricao_evento(id_usuario,id_evento)
);

CREATE TABLE IF NOT EXISTS ministra_atividade (
    id_usuario INTEGER NOT NULL,
    id_evento INTEGER NOT NULL,
    id_atividade INTEGER NOT NULL,

    mini_bio TEXT,
    instituicao TEXT NOT NULL,
    link_lattes TEXT ,

    PRIMARY KEY (id_usuario,id_evento,id_atividade),

    FOREIGN KEY (id_atividade,id_evento) REFERENCES atividade(id,id_evento),
    FOREIGN KEY (id_usuario) REFERENCES usuario(id)
);

CREATE TABLE IF NOT EXISTS sessao (
    -- apenas o hash SHA-256 (hex) do token é armazenado, nunca o token em si
    token_hash CHAR(64) PRIMARY KEY,
    -- sessões não fazem sentido sem o usuário, então são removidas junto com ele
    id_usuario INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    expira_em TIMESTAMPTZ NOT NULL
);

-- a criação de sessão remove as sessões expiradas do usuário, então o filtro
-- por id_usuario precisa de um índice (a PK só indexa token_hash)
CREATE INDEX IF NOT EXISTS idx_sessao_id_usuario ON sessao (id_usuario);

COMMIT;
