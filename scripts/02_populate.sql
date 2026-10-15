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

INSERT INTO usuario (id, nome, cpf, email, senha_hash, papel, data_nascimento) VALUES
    ( 1, 'Ana Souza',        '10433218100', 'ana.souza@exemplo.com',        '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'administrador', '1985-03-12'),
    ( 2, 'Bruno Lima',       '96001338914', 'bruno.lima@exemplo.com',       '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'administrador', '1990-07-25'),
    ( 3, 'Carla Mendes',     '08386379499', 'carla.mendes@exemplo.com',     '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '1998-01-30'),
    ( 4, 'Diego Ferreira',   '02654235114', 'diego.ferreira@exemplo.com',   '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '2001-11-05'),
    ( 5, 'Eduarda Rocha',    '16155940789', 'eduarda.rocha@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '1995-06-18'),
    ( 6, 'Felipe Araújo',    '81618495950', 'felipe.araujo@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '2003-09-09'),
    ( 7, 'Gabriela Nunes',   '31034131656', 'gabriela.nunes@exemplo.com',   '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '1999-12-01'),
    ( 8, 'Henrique Castro',  '47525534144', 'henrique.castro@exemplo.com',  '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '1978-04-22'),
    ( 9, 'Isabela Martins',  '92832764851', 'isabela.martins@exemplo.com',  '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '1982-08-14'),
    -- menores de idade, úteis para testar a classificação indicativa
    (10, 'João Pedro Alves', '35030564160', 'joao.alves@exemplo.com',       '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '2011-02-10'),
    (11, 'Larissa Barbosa',  '39537672409', 'larissa.barbosa@exemplo.com',  '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '2013-05-20'),
    (12, 'Marcos Vieira',    '23884969692', 'marcos.vieira@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '1988-10-03'),
    (13, 'Natália Gomes',    '53287101269', 'natalia.gomes@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '2000-02-29'),
    (14, 'Otávio Ribeiro',   '26916697857', 'otavio.ribeiro@exemplo.com',   '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '1993-03-15'),
    (15, 'Paula Cardoso',    '48018451427', 'paula.cardoso@exemplo.com',    '$argon2id$v=19$m=65536,t=3,p=4$+7pw/TBA6s1NhK0lSn/7Eg$0yafQECHiOF1bRSMFR9z9crR2efceS82nRKCRJewG2A', 'associado',     '1997-07-07');

SELECT setval(pg_get_serial_sequence('usuario', 'id'), (SELECT MAX(id) FROM usuario));

-- =====================================================================
-- Eventos
-- =====================================================================
-- localizacao é POINT(longitude, latitude)
-- banner e banner_thumbnail usam o picsum.photos com uma seed por evento: a mesma
-- seed devolve sempre a mesma imagem, em qualquer tamanho pedido

INSERT INTO evento (id, nome, descricao, data_hora_inicio, data_hora_fim, classificacao_indicativa, vagas, localizacao, banner, banner_thumbnail) VALUES
    (1, 'Semana Acadêmica de Computação 2026',
        'Uma semana de palestras, minicursos e mesas redondas sobre computação.',
        '2026-05-11 08:00:00-03', '2026-05-15 18:00:00-03', NULL, 100, POINT(-38.5743, -3.7461),
        'https://picsum.photos/seed/evento-1/1200/400', 'https://picsum.photos/seed/evento-1/400/225'),
    (2, 'Workshop de Banco de Dados',
        'Workshop prático sobre modelagem e consultas SQL.',
        '2026-08-20 13:00:00-03', '2026-08-20 18:00:00-03', 12, 30, POINT(-38.5743, -3.7461),
        'https://picsum.photos/seed/evento-2/1200/400', 'https://picsum.photos/seed/evento-2/400/225'),
    (3, 'Hackathon Cidades Inteligentes',
        'Maratona de 36 horas para desenvolver soluções para problemas urbanos.',
        '2026-11-07 09:00:00-03', '2026-11-08 18:00:00-03', 16, 40, POINT(-38.5267, -3.7319),
        'https://picsum.photos/seed/evento-3/1200/400', 'https://picsum.photos/seed/evento-3/400/225'),
    (4, 'Encontro de Segurança da Informação',
        'Palestras e um CTF introdutório sobre segurança ofensiva e defensiva.',
        '2026-12-03 08:00:00-03', '2026-12-04 17:00:00-03', 18, 50, NULL,
        'https://picsum.photos/seed/evento-4/1200/400', 'https://picsum.photos/seed/evento-4/400/225'),
    -- evento lotado: 3 vagas e 3 inscrições ativas (confirmadas + pendentes)
    (5, 'Oficina de Robótica para Iniciantes',
        'Oficina introdutória de robótica com kits Arduino.',
        '2026-10-25 08:00:00-03', '2026-10-25 12:00:00-03', 10, 3, POINT(-38.5431, -3.7172),
        'https://picsum.photos/seed/evento-5/1200/400', 'https://picsum.photos/seed/evento-5/400/225'),
    (6, 'Feira de Profissões em Tecnologia',
        'Estandes de empresas e conversas com profissionais da área.',
        '2027-01-20 09:00:00-03', '2027-01-20 17:00:00-03', NULL, 200, POINT(-38.5267, -3.7319),
        'https://picsum.photos/seed/evento-6/1200/400', 'https://picsum.photos/seed/evento-6/400/225'),
    (7, 'Bootcamp de Desenvolvimento Web',
        'Três dias de imersão em HTML, CSS, JavaScript e APIs REST.',
        '2027-02-08 08:00:00-03', '2027-02-10 18:00:00-03', 14, 35, POINT(-38.5743, -3.7461),
        'https://picsum.photos/seed/evento-7/1200/400', 'https://picsum.photos/seed/evento-7/400/225'),
    (8, 'Simpósio de Ciência de Dados',
        'Palestras sobre aprendizado de máquina, visualização e ética em dados.',
        '2027-03-15 08:30:00-03', '2027-03-16 17:30:00-03', NULL, 120, NULL,
        'https://picsum.photos/seed/evento-8/1200/400', 'https://picsum.photos/seed/evento-8/400/225');

-- ids foram inseridos explicitamente, então a sequência precisa ser ajustada
SELECT setval(pg_get_serial_sequence('evento', 'id'), (SELECT MAX(id) FROM evento));

-- =====================================================================
-- Atividades
-- =====================================================================
-- numero é UNIQUE na tabela inteira, então a numeração é global

INSERT INTO atividade (numero, id_evento, nome, descricao, sala, vagas, data_hora_inicio, data_hora_fim) VALUES
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

-- =====================================================================
-- Ministrantes
-- =====================================================================

INSERT INTO ministra_atividade (id_usuario, id_evento, numero_atividade, mini_bio, instituicao, link_lattes) VALUES
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

INSERT INTO inscricao_evento (id_usuario, id_evento, data_inscricao, status, comentario_administrador, comprovante_usuario, valor) VALUES
    -- Evento 1 (livre, R$ 50,00)
    ( 3, 1, '2026-04-02 10:15:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0003-1', 'UTF8'), 50.0),
    ( 4, 1, '2026-04-03 19:40:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0004-1', 'UTF8'), 50.0),
    ( 5, 1, '2026-04-05 08:05:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0005-1', 'UTF8'), 50.0),
    ( 6, 1, '2026-04-10 14:22:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0006-1', 'UTF8'), 50.0),
    ( 7, 1, '2026-04-11 16:00:00-03', 'confirmada', 'Comprovante legível, pagamento conferido.', convert_to('comprovante-pix-0007-1', 'UTF8'), 50.0),
    (10, 1, '2026-04-20 09:30:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0010-1', 'UTF8'), 50.0),
    (13, 1, '2026-04-21 21:10:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0013-1', 'UTF8'), 50.0),
    (14, 1, '2026-04-28 11:45:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0014-1', 'UTF8'), 50.0),
    (15, 1, '2026-05-01 13:00:00-03', 'cancelada',  'Cancelada a pedido da participante.', convert_to('comprovante-pix-0015-1', 'UTF8'), 50.0),

    -- Evento 2 (12+, R$ 30,00)
    ( 3, 2, '2026-07-28 10:00:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0003-2', 'UTF8'), 30.0),
    ( 4, 2, '2026-07-29 15:20:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0004-2', 'UTF8'), 30.0),
    ( 6, 2, '2026-08-01 09:00:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0006-2', 'UTF8'), 30.0),
    ( 7, 2, '2026-08-02 18:30:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0007-2', 'UTF8'), 30.0),
    (10, 2, '2026-08-05 20:00:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0010-2', 'UTF8'), 30.0),
    (13, 2, '2026-08-10 07:50:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0013-2', 'UTF8'), 30.0),
    (14, 2, '2026-08-12 12:00:00-03', 'cancelada',  'Valor informado diferente do comprovante.', convert_to('comprovante-pix-0014-2', 'UTF8'), 15.0),

    -- Evento 3 (16+, R$ 20,00)
    ( 3, 3, '2026-09-15 10:00:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0003-3', 'UTF8'), 20.0),
    ( 4, 3, '2026-09-16 11:30:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0004-3', 'UTF8'), 20.0),
    ( 5, 3, '2026-09-20 17:45:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0005-3', 'UTF8'), 20.0),
    (13, 3, '2026-09-22 08:10:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0013-3', 'UTF8'), 20.0),
    ( 6, 3, '2026-10-08 22:15:00-03', 'pendente',   NULL, convert_to('comprovante-pix-0006-3', 'UTF8'), 20.0),
    ( 7, 3, '2026-10-12 09:05:00-03', 'pendente',   NULL, NULL, 20.0),
    (14, 3, '2026-09-30 14:00:00-03', 'cancelada',  NULL, convert_to('comprovante-pix-0014-3', 'UTF8'), 20.0),

    -- Evento 4 (18+, R$ 80,00)
    ( 3, 4, '2026-10-01 10:00:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0003-4', 'UTF8'), 80.0),
    ( 5, 4, '2026-10-03 16:30:00-03', 'pendente',   NULL, convert_to('comprovante-pix-0005-4', 'UTF8'), 80.0),
    (13, 4, '2026-10-09 19:00:00-03', 'pendente',   'Aguardando envio de comprovante legível.', convert_to('comprovante-pix-0013-4', 'UTF8'), 80.0),
    (15, 4, '2026-10-14 08:20:00-03', 'pendente',   NULL, convert_to('comprovante-pix-0015-4', 'UTF8'), 80.0),

    -- Evento 5 (10+, 3 vagas, R$ 15,00) - lotado
    (10, 5, '2026-10-01 18:00:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0010-5', 'UTF8'), 15.0),
    (11, 5, '2026-10-02 18:30:00-03', 'confirmada', NULL, convert_to('comprovante-pix-0011-5', 'UTF8'), 15.0),
    ( 6, 5, '2026-10-10 10:00:00-03', 'pendente',   NULL, convert_to('comprovante-pix-0006-5', 'UTF8'), 15.0),
    ( 7, 5, '2026-10-04 13:15:00-03', 'cancelada',  'Comprovante não corresponde a um pagamento válido.', convert_to('comprovante-pix-0007-5', 'UTF8'), 15.0);

-- =====================================================================
-- Presenças
-- =====================================================================
-- apenas eventos já realizados (1 e 2) e apenas inscrições confirmadas

INSERT INTO presenca_atividade (id_usuario, id_evento, numero_atividade) VALUES
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

COMMIT;
