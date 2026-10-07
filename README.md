# Trabalho Prático de Fundamentos de Bancos de Dados - 2026.1

## Descrição

Esse repositório contém um sistema de gestão de eventos simples para exemplificar o
trabalho da disciplina de Fundamentos de Bancos de Dados.

Em [./docs/regras-de-negocio.md](./docs/regras-de-negocio.md) estão definidos os requisitos 
funcionais da aplicação.

## Etapas

### Diagrama ER
 
![./docs/diagrama-eer.jpeg](./docs/diagrama-eer.jpeg)

O relacionamento entre as entidades foi modelado utilizando a notação EER de ... Pelo draw.io.

### Modelo Relacional

A partir do modelo EER, as entidades e relacionamentos foram convertidas para o modelo relacional
que representa as mesmas relações de forma tabular e com chaves primárias e estrangeiras definidas:

```mermaid
erDiagram
    USUARIO {
        int id PK
        string nome
        string cpf
        string email
        boolean admin
        string senha_hash
        date data_nascimento
    }

    EVENTO {
        int id PK
        string nome
        string descricao
        int vagas
        string classificacao_indicativa
        datetime data_hora_inicio
        datetime data_hora_fim
        decimal latitude
        decimal longitude
    }

    ATIVIDADE {
        int id_evento PK, FK
        int numero PK
        string nome
        string descricao
        datetime data_hora_inicio
        datetime data_hora_fim
        string sala
    }

    INSCRICAO_EVENTO {
        int id_usuario PK, FK
        int id_evento PK, FK
        datetime data_inscricao
        boolean presenca
        string status
    }

    INSCRICAO_ATIVIDADE {
        int id_usuario PK, FK
        int id_evento PK, FK
        int numero_atividade PK, FK
        datetime data_inscricao
        boolean presenca
        string status
    }

    MINISTRANTE {
        int id_usuario PK, FK
        int id_evento PK, FK
        int numero_atividade PK, FK
        string mini_bio
        string instituicao
        string link_lattes
    }

    USUARIO ||--o{ INSCRICAO_EVENTO : "faz"
    EVENTO ||--o{ INSCRICAO_EVENTO : "recebe"
    EVENTO ||--|{ ATIVIDADE : "contem"
    INSCRICAO_EVENTO ||--o{ INSCRICAO_ATIVIDADE : "participa de"
    ATIVIDADE ||--o{ INSCRICAO_ATIVIDADE : "tem inscritos"
    USUARIO ||--o{ MINISTRANTE : "ministra"
    ATIVIDADE ||--|{ MINISTRANTE : "Ministrada por"
```

