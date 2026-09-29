BEGIN;

CREATE TABLE IF NOT EXISTS usuario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome TEXT NOT NULL,
    cpf CHAR(11) UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    admin BOOLEAN NOT NULL DEFAULT false,
    data_nascimento DATE NOT NULL
    -- idade não pode ser uma coluna virtual porque depende da data atual (função mutável)
    -- por isso ela é adicionada em uma view
);

CREATE OR REPLACE VIEW usuario_com_idade AS (
    SELECT id, nome, cpf, email, EXTRACT(YEARS FROM AGE(data_nascimento)) as idade FROM usuario
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
    localizacao POINT -- utilizando o tipo de dados padrão do postgres
);

CREATE TABLE IF NOT EXISTS atividade (
    numero INTEGER UNIQUE NOT NULL,
    id_evento INTEGER REFERENCES evento(id) NOT NULL,
    nome TEXT NOT NULL,
    descricao TEXT,
    sala TEXT NOT NULL, 
    vagas INTEGER NOT NULL,
    data_hora_inicio TIMESTAMPTZ NOT NULL,
    data_hora_fim TIMESTAMPTZ NOT NULL,

    PRIMARY KEY (numero,id_evento)
);

CREATE TABLE IF NOT EXISTS inscricao_evento (
    id_usuario UUID REFERENCES usuario(id) NOT NULL,
    id_evento INTEGER REFERENCES evento(id) NOT NULL,
    data_inscricao TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT "pendente",
    presenca BOOLEAN NOT NULL DEFAULT false,

    PRIMARY KEY (id_usuario,id_evento)
);

CREATE TABLE IF NOT EXISTS inscricao_atividade (
    id_usuario UUID NOT NULL,
    id_evento INTEGER NOT NULL,
    numero_atividade INTEGER NOT NULL,
    data_inscricao TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT "pendente",
    presenca BOOLEAN NOT NULL DEFAULT false,

    PRIMARY KEY (id_usuario,id_evento,numero_atividade),

    FOREIGN KEY (numero_atividade,id_evento) REFERENCES atividade(numero,id_evento),

    -- utilizando uma chave estrangeira composta para referenciar apenas
    -- usuários que participam de um evento como participantes
    FOREIGN KEY (id_usuario,id_evento) REFERENCES inscricao_evento(id_usuario,id_evento)
);

CREATE TABLE IF NOT EXISTS ministra_atividade (
    id_usuario UUID NOT NULL,
    id_evento INTEGER NOT NULL,
    numero_atividade INTEGER NOT NULL,

    mini_bio TEXT,
    instituicao TEXT NOT NULL,
    link_lattes TEXT ,

    PRIMARY KEY (id_usuario,id_evento,numero_atividade),

    FOREIGN KEY (numero_atividade,id_evento) REFERENCES atividade(numero,id_evento),
    -- utilizando uma chave estrangeira composta para referenciar qualquer
    -- usuário como ministrante
    FOREIGN KEY (id_usuario) REFERENCES usuario(id)
);
   
COMMIT;
