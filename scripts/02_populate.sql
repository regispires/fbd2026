BEGIN;

-- Dados fictícios para desenvolvimento/testes.
-- Executado automaticamente pelo container do postgres (docker-entrypoint-initdb.d)
-- após o 01_create_tables.sql, apenas quando o volume do banco está vazio.
--
-- Os dados respeitam as regras de negócio (docs/regras-de-negocio.md):
--   - todo evento possui ao menos uma atividade e toda atividade ao menos um ministrante
--   - o horário das atividades está contido no horário do evento
--   - inscrições respeitam a classificação indicativa e o número de vagas
--   - presenças só existem para inscrições confirmadas em eventos que já ocorreram
--
-- Todos os usuários têm a senha 'senha123'. O hash é argon2id gerado pelo pwdlib
-- (o mesmo hasher usado em app/database/repository/user.py), por isso é fixo aqui.

-- =====================================================================
-- Usuários
-- =====================================================================
-- ids inseridos explicitamente para facilitar a referência nas demais tabelas e nos testes

INSERT INTO usuario (id, nome, cpf, email, senha_hash, papel, sexo, estado_civil, data_nascimento) VALUES
    ( 1, 'Ana Souza',        '10433218100', 'ana.souza@exemplo.com',        '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'administrador', 'F', 'C', '1985-03-12'),
    ( 2, 'Bruno Lima',       '96001338914', 'bruno.lima@exemplo.com',       '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'administrador', 'M', 'C', '1990-07-25'),
    ( 3, 'Carla Mendes',     '08386379499', 'carla.mendes@exemplo.com',     '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'F', 'S', '1998-01-30'),
    ( 4, 'Diego Ferreira',   '02654235114', 'diego.ferreira@exemplo.com',   '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'M', 'S', '2001-11-05'),
    ( 5, 'Eduarda Rocha',    '16155940789', 'eduarda.rocha@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'F', 'C', '1995-06-18'),
    ( 6, 'Felipe Araújo',    '81618495950', 'felipe.araujo@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'M', 'S', '2003-09-09'),
    ( 7, 'Gabriela Nunes',   '31034131656', 'gabriela.nunes@exemplo.com',   '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'F', 'S', '1999-12-01'),
    ( 8, 'Henrique Castro',  '47525534144', 'henrique.castro@exemplo.com',  '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'M', 'D', '1978-04-22'),
    ( 9, 'Isabela Martins',  '92832764851', 'isabela.martins@exemplo.com',  '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'F', 'C', '1982-08-14'),
    -- menores de idade, úteis para testar a classificação indicativa
    (10, 'João Pedro Alves', '35030564160', 'joao.alves@exemplo.com',       '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'M', 'S', '2011-02-10'),
    (11, 'Larissa Barbosa',  '39537672409', 'larissa.barbosa@exemplo.com',  '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'F', 'S', '2013-05-20'),
    (12, 'Marcos Vieira',    '23884969692', 'marcos.vieira@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'M', 'D', '1988-10-03'),
    (13, 'Natália Gomes',    '53287101269', 'natalia.gomes@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'O', 'S', '2000-02-29'),
    (14, 'Otávio Ribeiro',   '26916697857', 'otavio.ribeiro@exemplo.com',   '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'M', 'C', '1993-03-15'),
    (15, 'Paula Cardoso',    '48018451427', 'paula.cardoso@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     'F', 'S', '1997-07-07');

SELECT setval(pg_get_serial_sequence('usuario', 'id'), (SELECT MAX(id) FROM usuario));

-- =====================================================================
-- Eventos
-- =====================================================================
-- localizacao é POINT(longitude, latitude)
-- banner e banner_thumbnail usam o picsum.photos com uma seed por evento: a mesma
-- seed devolve sempre a mesma imagem, em qualquer tamanho pedido

INSERT INTO evento (id, nome, descricao, data_hora_inicio, data_hora_fim, classificacao_indicativa, vagas, localizacao, banner, banner_thumbnail, valor) VALUES
    (1, 'Semana Acadêmica de Computação 2026',
        'Uma semana de palestras, minicursos e mesas redondas sobre computação.',
        '2026-05-11 08:00:00-03', '2026-05-15 18:00:00-03', NULL, 100, POINT(-38.5743, -3.7461),
        'https://picsum.photos/seed/evento-1/1200/400', 'https://picsum.photos/seed/evento-1/400/225', 50.0),
    (2, 'Workshop de Banco de Dados',
        'Workshop prático sobre modelagem e consultas SQL.',
        '2026-08-20 13:00:00-03', '2026-08-20 18:00:00-03', 12, 30, POINT(-38.5743, -3.7461),
        'https://picsum.photos/seed/evento-2/1200/400', 'https://picsum.photos/seed/evento-2/400/225', 30.0),
    (3, 'Hackathon Cidades Inteligentes',
        'Maratona de 36 horas para desenvolver soluções para problemas urbanos.',
        '2026-11-07 09:00:00-03', '2026-11-08 18:00:00-03', 16, 40, POINT(-38.5267, -3.7319),
        'https://picsum.photos/seed/evento-3/1200/400', 'https://picsum.photos/seed/evento-3/400/225', 20.0),
    (4, 'Encontro de Segurança da Informação',
        'Palestras e um CTF introdutório sobre segurança ofensiva e defensiva.',
        '2026-12-03 08:00:00-03', '2026-12-04 17:00:00-03', 18, 50, NULL,
        'https://picsum.photos/seed/evento-4/1200/400', 'https://picsum.photos/seed/evento-4/400/225', 80.0),
    -- evento lotado: 3 vagas e 3 inscrições ativas (confirmadas + pendentes)
    (5, 'Oficina de Robótica para Iniciantes',
        'Oficina introdutória de robótica com kits Arduino.',
        '2026-10-25 08:00:00-03', '2026-10-25 12:00:00-03', 10, 3, POINT(-38.5431, -3.7172),
        'https://picsum.photos/seed/evento-5/1200/400', 'https://picsum.photos/seed/evento-5/400/225', 15.0),
    (6, 'Feira de Profissões em Tecnologia',
        'Estandes de empresas e conversas com profissionais da área.',
        '2027-01-20 09:00:00-03', '2027-01-20 17:00:00-03', NULL, 200, POINT(-38.5267, -3.7319),
        'https://picsum.photos/seed/evento-6/1200/400', 'https://picsum.photos/seed/evento-6/400/225', 0.0),
    (7, 'Bootcamp de Desenvolvimento Web',
        'Três dias de imersão em HTML, CSS, JavaScript e APIs REST.',
        '2027-02-08 08:00:00-03', '2027-02-10 18:00:00-03', 14, 35, POINT(-38.5743, -3.7461),
        'https://picsum.photos/seed/evento-7/1200/400', 'https://picsum.photos/seed/evento-7/400/225', 60.0),
    (8, 'Simpósio de Ciência de Dados',
        'Palestras sobre aprendizado de máquina, visualização e ética em dados.',
        '2027-03-15 08:30:00-03', '2027-03-16 17:30:00-03', NULL, 120, NULL,
        'https://picsum.photos/seed/evento-8/1200/400', 'https://picsum.photos/seed/evento-8/400/225', 40.0);

-- ids foram inseridos explicitamente, então a sequência precisa ser ajustada
SELECT setval(pg_get_serial_sequence('evento', 'id'), (SELECT MAX(id) FROM evento));

-- =====================================================================
-- Atividades
-- =====================================================================
-- ids inseridos explicitamente para facilitar a referência nas demais tabelas

INSERT INTO atividade (id, id_evento, nome, descricao, sala, vagas, data_hora_inicio, data_hora_fim) VALUES
    -- Evento 1
    (1,  1, 'Abertura: IA na educação', 'Palestra de abertura sobre o uso de IA em sala de aula.', 'Auditório', 100, '2026-05-11 08:00:00-03', '2026-05-11 10:00:00-03'),
    (2,  1, 'Minicurso de Python', 'Introdução à linguagem Python.', 'Laboratório 1', 30, '2026-05-12 14:00:00-03', '2026-05-12 18:00:00-03'),
    (3,  1, 'Minicurso de Git', 'Controle de versão com Git e GitHub.', 'Laboratório 2', 30, '2026-05-13 14:00:00-03', '2026-05-13 18:00:00-03'),
    (4,  1, 'Mesa redonda: mercado de trabalho', NULL, 'Auditório', 100, '2026-05-15 15:00:00-03', '2026-05-15 18:00:00-03'),
    -- Evento 2
    (5,  2, 'Modelagem EER na prática', 'Do minimundo ao diagrama EER.', 'Sala 201', 30, '2026-08-20 13:00:00-03', '2026-08-20 15:30:00-03'),
    (6,  2, 'SQL avançado: CTEs e window functions', NULL, 'Laboratório 3', 30, '2026-08-20 15:30:00-03', '2026-08-20 18:00:00-03'),
    -- Evento 3
    (7,  3, 'Abertura e formação de equipes', NULL, 'Auditório', 40, '2026-11-07 09:00:00-03', '2026-11-07 10:30:00-03'),
    (8,  3, 'Mentoria técnica', 'Mentores disponíveis para tirar dúvidas das equipes.', 'Sala 105', 40, '2026-11-07 14:00:00-03', '2026-11-07 20:00:00-03'),
    (9,  3, 'Apresentação dos projetos', 'Pitch final das equipes para a banca.', 'Auditório', 40, '2026-11-08 14:00:00-03', '2026-11-08 18:00:00-03'),
    -- Evento 4
    (10, 4, 'Palestra: Engenharia social', NULL, 'Auditório', 50, '2026-12-03 09:00:00-03', '2026-12-03 11:00:00-03'),
    (11, 4, 'CTF introdutório', 'Competição capture the flag para iniciantes.', 'Laboratório 1', 25, '2026-12-04 08:00:00-03', '2026-12-04 17:00:00-03'),
    -- Evento 5
    (12, 5, 'Montando seu primeiro robô', NULL, 'Laboratório de Robótica', 3, '2026-10-25 08:00:00-03', '2026-10-25 12:00:00-03'),
    -- Evento 6
    (13, 6, 'Painel: primeiros passos na carreira', NULL, 'Auditório', 200, '2027-01-20 10:00:00-03', '2027-01-20 12:00:00-03'),
    -- Evento 7
    (14, 7, 'Fundamentos de HTML e CSS', NULL, 'Laboratório 1', 35, '2027-02-08 08:00:00-03', '2027-02-08 18:00:00-03'),
    (15, 7, 'Construindo uma API REST', 'Do zero ao deploy de uma API simples.', 'Laboratório 1', 35, '2027-02-10 08:00:00-03', '2027-02-10 18:00:00-03'),
    -- Evento 8
    (16, 8, 'Abertura: ética em dados', NULL, 'Auditório', 120, '2027-03-15 08:30:00-03', '2027-03-15 10:00:00-03');

-- ids foram inseridos explicitamente, então a sequência precisa ser ajustada
SELECT setval(pg_get_serial_sequence('atividade', 'id'), (SELECT MAX(id) FROM atividade));

-- =====================================================================
-- Ministrantes
-- =====================================================================

INSERT INTO ministra_atividade (id_usuario, id_evento, id_atividade, mini_bio, instituicao, link_lattes) VALUES
    ( 9, 1, 1,  'Professora de Ciência da Computação, pesquisa IA aplicada à educação.', 'Universidade Federal do Ceará', 'http://lattes.cnpq.br/0000000000000009'),
    (12, 1, 2,  'Desenvolvedor backend há 10 anos.', 'Empresa Exemplo LTDA', NULL),
    ( 5, 1, 3,  'Mestranda em Engenharia de Software.', 'Universidade Federal do Ceará', 'http://lattes.cnpq.br/0000000000000005'),
    ( 8, 1, 4,  'Professor e consultor de carreira em TI.', 'Instituto Federal do Ceará', 'http://lattes.cnpq.br/0000000000000008'),
    (12, 1, 4,  'Desenvolvedor backend há 10 anos.', 'Empresa Exemplo LTDA', NULL),
    ( 8, 2, 5,  'Professor de Banco de Dados.', 'Instituto Federal do Ceará', 'http://lattes.cnpq.br/0000000000000008'),
    ( 1, 2, 6,  'DBA e administradora do sistema de eventos.', 'Universidade Federal do Ceará', NULL),
    ( 2, 3, 7,  NULL, 'Universidade Federal do Ceará', NULL),
    ( 9, 3, 8,  'Professora de Ciência da Computação.', 'Universidade Federal do Ceará', 'http://lattes.cnpq.br/0000000000000009'),
    (12, 3, 8,  'Desenvolvedor backend há 10 anos.', 'Empresa Exemplo LTDA', NULL),
    ( 2, 3, 9,  NULL, 'Universidade Federal do Ceará', NULL),
    (14, 4, 10, 'Analista de segurança da informação.', 'Empresa Segura S.A.', NULL),
    (14, 4, 11, 'Analista de segurança da informação.', 'Empresa Segura S.A.', NULL),
    ( 8, 5, 12, 'Professor e entusiasta de robótica.', 'Instituto Federal do Ceará', 'http://lattes.cnpq.br/0000000000000008'),
    ( 8, 6, 13, 'Professor e consultor de carreira em TI.', 'Instituto Federal do Ceará', 'http://lattes.cnpq.br/0000000000000008'),
    (12, 7, 14, 'Desenvolvedor backend há 10 anos.', 'Empresa Exemplo LTDA', NULL),
    (12, 7, 15, 'Desenvolvedor backend há 10 anos.', 'Empresa Exemplo LTDA', NULL),
    ( 9, 8, 16, 'Professora de Ciência da Computação, pesquisa IA aplicada à educação.', 'Universidade Federal do Ceará', 'http://lattes.cnpq.br/0000000000000009');

-- =====================================================================
-- Inscrições
-- =====================================================================
-- comprovante_usuario contém apenas bytes de exemplo, não um arquivo real

INSERT INTO inscricao_evento (id_usuario, id_evento, data_inscricao, status, comentario_administrador, comprovante_usuario, valor, meia) VALUES
    -- Evento 1 (R$ 50,00)
    ( 3, 1, '2026-04-02 10:15:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0003-1', 'UTF8'), 50.0, FALSE),
    ( 4, 1, '2026-04-03 19:40:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0004-1', 'UTF8'), 50.0, FALSE),
    ( 5, 1, '2026-04-05 08:05:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0005-1', 'UTF8'), 50.0, FALSE),
    ( 6, 1, '2026-04-10 14:22:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0006-1', 'UTF8'), 50.0, FALSE),
    ( 7, 1, '2026-04-11 16:00:00-03', 'confirmada', 'Comprovante legível, pagamento conferido.', convert_to('%PDF-1.4 comprovante-pix-0007-1', 'UTF8'), 50.0, FALSE),
    (10, 1, '2026-04-20 09:30:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0010-1', 'UTF8'), 50.0, FALSE),
    (13, 1, '2026-04-21 21:10:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0013-1', 'UTF8'), 50.0, FALSE),
    (14, 1, '2026-04-28 11:45:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0014-1', 'UTF8'), 50.0, FALSE),
    (15, 1, '2026-05-01 13:00:00-03', 'cancelada',  'Cancelada a pedido da participante.', convert_to('%PDF-1.4 comprovante-pix-0015-1', 'UTF8'), 50.0, FALSE),

    -- Evento 2 (R$ 30,00) - inclui meia-entrada confirmada e meia-entrada cancelada
    ( 3, 2, '2026-07-28 10:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0003-2', 'UTF8'), 30.0, FALSE),
    ( 4, 2, '2026-07-29 15:20:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0004-2', 'UTF8'), 30.0, FALSE),
    ( 6, 2, '2026-08-01 09:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0006-2', 'UTF8'), 15.0, TRUE),
    ( 7, 2, '2026-08-02 18:30:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0007-2', 'UTF8'), 30.0, FALSE),
    (10, 2, '2026-08-05 20:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0010-2', 'UTF8'), 30.0, FALSE),
    (13, 2, '2026-08-10 07:50:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0013-2', 'UTF8'), 30.0, FALSE),
    (14, 2, '2026-08-12 12:00:00-03', 'cancelada',  'Valor informado diferente do comprovante.', convert_to('%PDF-1.4 comprovante-pix-0014-2', 'UTF8'), 15.0, TRUE),

    -- Evento 3 (R$ 20,00) - inclui duas pendentes para avaliação
    ( 3, 3, '2026-09-15 10:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0003-3', 'UTF8'), 20.0, FALSE),
    ( 4, 3, '2026-09-16 11:30:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0004-3', 'UTF8'), 20.0, FALSE),
    ( 5, 3, '2026-09-20 17:45:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0005-3', 'UTF8'), 20.0, FALSE),
    (13, 3, '2026-09-22 08:10:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0013-3', 'UTF8'), 20.0, FALSE),
    ( 6, 3, '2026-10-08 22:15:00-03', 'pendente',   NULL, convert_to('%PDF-1.4 comprovante-pix-0006-3', 'UTF8'), 20.0, FALSE),
    ( 7, 3, '2026-10-12 09:05:00-03', 'pendente',   NULL, NULL, 20.0, FALSE),
    (14, 3, '2026-09-30 14:00:00-03', 'cancelada',  NULL, convert_to('%PDF-1.4 comprovante-pix-0014-3', 'UTF8'), 20.0, FALSE),

    -- Evento 4 (R$ 80,00) - inclui três pendentes (uma meia-entrada)
    ( 3, 4, '2026-10-01 10:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0003-4', 'UTF8'), 80.0, FALSE),
    ( 5, 4, '2026-10-03 16:30:00-03', 'pendente',   NULL, convert_to('%PDF-1.4 comprovante-pix-0005-4', 'UTF8'), 80.0, FALSE),
    (13, 4, '2026-10-09 19:00:00-03', 'pendente',   'Aguardando envio de comprovante legível.', convert_to('%PDF-1.4 comprovante-pix-0013-4', 'UTF8'), 40.0, TRUE),
    (15, 4, '2026-10-14 08:20:00-03', 'pendente',   NULL, convert_to('%PDF-1.4 comprovante-pix-0015-4', 'UTF8'), 80.0, FALSE),

    -- Evento 5 (R$ 15,00) - lotado
    (10, 5, '2026-10-01 18:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0010-5', 'UTF8'), 15.0, FALSE),
    (11, 5, '2026-10-02 18:30:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0011-5', 'UTF8'), 15.0, FALSE),
    ( 6, 5, '2026-10-10 10:00:00-03', 'pendente',   NULL, convert_to('%PDF-1.4 comprovante-pix-0006-5', 'UTF8'), 15.0, FALSE),
    ( 7, 5, '2026-10-04 13:15:00-03', 'cancelada',  'Comprovante não corresponde a um pagamento válido.', convert_to('%PDF-1.4 comprovante-pix-0007-5', 'UTF8'), 15.0, FALSE);

-- =====================================================================
-- Presenças
-- =====================================================================
-- apenas eventos já realizados (1 e 2) e apenas inscrições confirmadas

INSERT INTO presenca_atividade (id_usuario, id_evento, id_atividade) VALUES
    -- Evento 1
    ( 3, 1, 1),
    ( 3, 1, 2),
    ( 3, 1, 4),
    ( 4, 1, 1),
    ( 4, 1, 2),
    ( 4, 1, 3),
    ( 4, 1, 4),
    ( 5, 1, 1),
    ( 6, 1, 2),
    ( 6, 1, 3),
    ( 7, 1, 1),
    ( 7, 1, 4),
    (10, 1, 3),
    (13, 1, 1),
    (13, 1, 2),
    (13, 1, 3),
    (14, 1, 4),
    -- Evento 2
    ( 3, 2, 5),
    ( 3, 2, 6),
    ( 4, 2, 5),
    ( 6, 2, 5),
    ( 6, 2, 6),
    ( 7, 2, 6),
    (10, 2, 5),
    (13, 2, 5),
    (13, 2, 6);

-- =====================================================================
-- Dados extras para exercitar a paginação
-- =====================================================================
-- A escala acima deixa cada listagem em uma única página. As entradas abaixo
-- acrescentam eventos, atividades e inscrições suficientes para que os
-- paginadores apareçam (artificial em parte, mas respeitando as regras de
-- negócio documentadas). Válido apenas para um volume novo do banco.

-- Eventos 9..13 (todos futuros, sem presenças)
INSERT INTO evento (id, nome, descricao, data_hora_inicio, data_hora_fim, classificacao_indicativa, vagas, localizacao, banner, banner_thumbnail, valor) VALUES
    ( 9, 'Curso de Introdução ao Linux',
        'Um dia de instalação, linha de comando e primeiros scripts.',
        '2027-04-05 08:00:00-04', '2027-04-05 18:00:00-04', NULL, 40, POINT(-38.5743, -3.7461),
        'https://picsum.photos/seed/evento-9/1200/400', 'https://picsum.photos/seed/evento-9/400/225', 25.0),
    (10, 'Treino para Maratona de Programação',
        'Um dia de listas, grafos e programação dinâmica para o competitivo.',
        '2027-04-24 09:00:00-04', '2027-04-24 17:00:00-04', 14, 60, POINT(-38.5267, -3.7319),
        'https://picsum.photos/seed/evento-10/1200/400', 'https://picsum.photos/seed/evento-10/400/225', 10.0),
    (11, 'Fórum de Empreendedorismo Digital',
        'Conversas sobre produtos digitais e startups acadêmicas.',
        '2027-05-06 13:00:00-04', '2027-05-06 20:00:00-04', NULL, 80, POINT(-38.5431, -3.7172),
        'https://picsum.photos/seed/evento-11/1200/400', 'https://picsum.photos/seed/evento-11/400/225', 0.0),
    (12, 'Oficina de UX/UI Design',
        'Dois dias de pesquisa com usuários, wireframes e protótipos.',
        '2027-05-21 09:00:00-04', '2027-05-22 17:00:00-04', NULL, 25, NULL,
        'https://picsum.photos/seed/evento-12/1200/400', 'https://picsum.photos/seed/evento-12/400/225', 35.0),
    (13, 'Conferência de Software Livre',
        'Trilhas sobre comunidades, contribuição e empacotamento.',
        '2027-06-10 08:00:00-04', '2027-06-11 18:00:00-04', NULL, 150, POINT(-38.5743, -3.7461),
        'https://picsum.photos/seed/evento-13/1200/400', 'https://picsum.photos/seed/evento-13/400/225', 45.0);

SELECT setval(pg_get_serial_sequence('evento', 'id'), (SELECT MAX(id) FROM evento));

-- Atividades extras: 17..26 nos eventos novos e 27..33 na Semana Acadêmica
-- (evento 1, já realizado: as presenças abaixo dependem de atividades passadas)
INSERT INTO atividade (id, id_evento, nome, descricao, sala, vagas, data_hora_inicio, data_hora_fim) VALUES
    -- Evento 9
    (17,  9, 'Instalação e primeiro contato', 'Partições, usuários e primeiros comandos.', 'Sala 101', 40, '2027-04-05 08:00:00-04', '2027-04-05 12:00:00-04'),
    (18,  9, 'Linha de comando na prática', 'Compactação, permissões, pipes e scripts simples.', 'Sala 101', 40, '2027-04-05 13:00:00-04', '2027-04-05 18:00:00-04'),
    -- Evento 10
    (19, 10, 'Treino: listas e grafos', 'Problemas clássicos e dobramentos de técnicas.', 'Laboratório 3', 60, '2027-04-24 09:00:00-04', '2027-04-24 12:00:00-04'),
    (20, 10, 'Treino: programação dinâmica', 'Recorrências e otimizações para o competitivo.', 'Laboratório 3', 60, '2027-04-24 13:00:00-04', '2027-04-24 17:00:00-04'),
    -- Evento 11
    (21, 11, 'Painel: startups de tecnologia', 'Fundadores contam trajetórias e aprendizados.', 'Auditório', 80, '2027-05-06 14:00:00-04', '2027-05-06 16:00:00-04'),
    -- Evento 12
    (22, 12, 'Princípios de UX', 'Pesquisa com usuários e arquitetura de informação.', 'Sala 202', 25, '2027-05-21 09:00:00-04', '2027-05-21 12:00:00-04'),
    (23, 12, 'Prototipação no Figma', 'Do wireframe ao protótipo navegável.', 'Sala 202', 25, '2027-05-21 13:00:00-04', '2027-05-21 17:00:00-04'),
    -- Evento 13
    (24, 13, 'Abertura: software livre e comunidade', NULL, 'Auditório', 150, '2027-06-10 08:00:00-04', '2027-06-10 10:00:00-04'),
    (25, 13, 'Workshop: contribuindo para projetos open source', 'Pull requests reais em projetos da comunidade.', 'Laboratório 2', 40, '2027-06-10 10:30:00-04', '2027-06-10 12:30:00-04'),
    (26, 13, 'Workshop: empacotamento de software', 'Pacotes, dependências e repositórios.', 'Laboratório 2', 40, '2027-06-10 14:00:00-04', '2027-06-10 18:00:00-04'),
    -- Evento 1: mais atividades da semana (a listagem de atividades fica com 2 páginas)
    (27,  1, 'Palestra: computação quântica para curiosos', NULL, 'Auditório', 100, '2026-05-11 14:00:00-03', '2026-05-11 16:00:00-03'),
    (28,  1, 'Minicurso: introdução ao Rust', 'Tipos, ownership e segurança de memória.', 'Laboratório 2', 30, '2026-05-12 08:00:00-03', '2026-05-12 12:00:00-03'),
    (29,  1, 'Roda de conversa: mulheres na computação', NULL, 'Auditório', 100, '2026-05-12 16:00:00-03', '2026-05-12 18:00:00-03'),
    (30,  1, 'Oficina: automação com Python', 'Scripts que economizam horas de trabalho.', 'Laboratório 1', 30, '2026-05-13 08:00:00-03', '2026-05-13 12:00:00-03'),
    (31,  1, 'Palestra: cloud e SRE', 'Confiabilidade e operação em escala.', 'Auditório', 100, '2026-05-13 19:00:00-03', '2026-05-13 21:00:00-03'),
    (32,  1, 'Minicurso: Linux básico', 'Terminal e pacotes para iniciantes.', 'Laboratório 2', 30, '2026-05-14 08:00:00-03', '2026-05-14 12:00:00-03'),
    (33,  1, 'Competição de programação interna', 'Maratona curta entre equipes do campus.', 'Laboratório 3', 50, '2026-05-14 14:00:00-03', '2026-05-14 18:00:00-03');

SELECT setval(pg_get_serial_sequence('atividade', 'id'), (SELECT MAX(id) FROM atividade));

INSERT INTO ministra_atividade (id_usuario, id_evento, id_atividade, mini_bio, instituicao, link_lattes) VALUES
    -- Eventos 9..13
    (14,  9, 17, 'Administra sistemas Linux há doze anos.', 'Empresa Segura S.A.', NULL),
    ( 9,  9, 18, 'Professora de Sistemas Operacionais.', 'Universidade Federal do Ceará', NULL),
    ( 2, 10, 19, 'Treinador da equipe de maratona.', 'Universidade Federal do Ceará', NULL),
    ( 9, 10, 20, 'Professora de algoritmos.', 'Universidade Federal do Ceará', NULL),
    ( 8, 11, 21, 'Consultor de carreira em TI.', 'Instituto Federal do Ceará', 'http://lattes.cnpq.br/0000000000000008'),
    ( 5, 12, 22, 'Pesquisadora de interação humano-computador.', 'Universidade Federal do Ceará', 'http://lattes.cnpq.br/0000000000000005'),
    (12, 12, 23, 'Designer de produto há 10 anos.', 'Empresa Exemplo LTDA', NULL),
    ( 9, 13, 24, 'Mantenedora de projetos educacionais livres.', 'Universidade Federal do Ceará', 'http://lattes.cnpq.br/0000000000000009'),
    (12, 13, 25, 'Contribuidor de projetos open source.', 'Empresa Exemplo LTDA', NULL),
    (14, 13, 26, 'Empacotador de distribuição Linux.', 'Empresa Segura S.A.', NULL),
    -- Evento 1: ministrantes das atividades extras (27..33)
    ( 9, 1, 27, 'Professora de Ciência da Computação.', 'Universidade Federal do Ceará', 'http://lattes.cnpq.br/0000000000000009'),
    (12, 1, 28, 'Desenvolvedor backend há 10 anos.', 'Empresa Exemplo LTDA', NULL),
    ( 1, 1, 29, 'Administradora do sistema de eventos.', 'Universidade Federal do Ceará', NULL),
    ( 5, 1, 30, 'Mestranda em Engenharia de Software.', 'Universidade Federal do Ceará', 'http://lattes.cnpq.br/0000000000000005'),
    ( 8, 1, 31, 'Professor e consultor de carreira em TI.', 'Instituto Federal do Ceará', 'http://lattes.cnpq.br/0000000000000008'),
    (14, 1, 32, 'Analista de infraestrutura.', 'Empresa Segura S.A.', NULL),
    ( 2, 1, 33, 'Treinador da equipe de maratona.', 'Universidade Federal do Ceará', NULL);

-- Mais inscrições: o evento 1 fica com 15 (página dupla no painel) e a
-- Carla Mendes (usuário 3) fica com 11 inscrições (página dupla em "Minhas
-- inscrições"). Valores derivados do preço do evento (cheio ou meia).
INSERT INTO inscricao_evento (id_usuario, id_evento, data_inscricao, status, comentario_administrador, comprovante_usuario, valor, meia) VALUES
    -- Evento 1: de 9 para 15 inscrições
    ( 1, 1, '2026-04-12 09:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0001-1', 'UTF8'), 50.0, FALSE),
    ( 2, 1, '2026-04-14 10:30:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0002-1', 'UTF8'), 25.0, TRUE),
    ( 8, 1, '2026-04-16 15:45:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0008-1', 'UTF8'), 50.0, FALSE),
    ( 9, 1, '2026-04-18 11:20:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0009-1', 'UTF8'), 50.0, FALSE),
    (11, 1, '2026-04-22 09:10:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0011-1', 'UTF8'), 25.0, TRUE),
    (12, 1, '2026-04-26 14:00:00-03', 'cancelada',  'Comprovante ilegível.', convert_to('%PDF-1.4 comprovante-pix-0012-1', 'UTF8'), 50.0, FALSE),

    -- Carla Mendes (3) em eventos 7..13 (já tem 1, 2, 3 e 4)
    ( 3, 7, '2026-10-15 10:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0003-7', 'UTF8'), 60.0, FALSE),
    ( 3, 8, '2026-10-16 10:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0003-8', 'UTF8'), 40.0, FALSE),
    ( 3, 9, '2026-10-18 10:00:00-03', 'pendente',   NULL, convert_to('%PDF-1.4 comprovante-pix-0003-9', 'UTF8'), 25.0, FALSE),
    ( 3,10, '2026-10-19 10:00:00-03', 'pendente',   NULL, convert_to('%PDF-1.4 comprovante-pix-0003-10', 'UTF8'), 10.0, FALSE),
    ( 3,11, '2026-10-20 10:00:00-03', 'confirmada', NULL, NULL, 0.0, FALSE),
    ( 3,12, '2026-10-22 10:00:00-03', 'pendente',   NULL, convert_to('%PDF-1.4 comprovante-pix-0003-12', 'UTF8'), 35.0, FALSE),
    ( 3,13, '2026-10-25 10:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0003-13', 'UTF8'), 45.0, FALSE),
    ( 4, 9, '2026-10-20 08:30:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0004-9', 'UTF8'), 25.0, FALSE),
    ( 6,10, '2026-10-21 12:00:00-03', 'confirmada', NULL, convert_to('%PDF-1.4 comprovante-pix-0006-10', 'UTF8'), 10.0, FALSE),
    ( 7,13, '2026-10-24 16:40:00-03', 'pendente',   NULL, convert_to('%PDF-1.4 comprovante-pix-0007-13', 'UTF8'), 45.0, FALSE);

-- Presenças extra: Diego Ferreira (4) em praticamente toda a Semana
-- Acadêmica — 11 presenças no evento 1 (a página de presenças dele fica
-- com 2 páginas). Atividades já passadas.
INSERT INTO presenca_atividade (id_usuario, id_evento, id_atividade) VALUES
    ( 4, 1, 27),
    ( 4, 1, 28),
    ( 4, 1, 29),
    ( 4, 1, 30),
    ( 4, 1, 31),
    ( 4, 1, 32),
    ( 4, 1, 33);

COMMIT;
