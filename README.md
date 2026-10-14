# Trabalho Prático de Fundamentos de Bancos de Dados - 2026.1

## Descrição

Esse repositório contém um sistema de gestão de eventos simples para exemplificar o
trabalho da disciplina de Fundamentos de Bancos de Dados.

Em [./docs/regras-de-negocio.md](./docs/regras-de-negocio.md) estão definidos os requisitos 
funcionais da aplicação.

## Etapas

### Diagrama ER
 
![./docs/diagrama-eer.jpg](./docs/diagrama-eer.jpg)

O relacionamento entre as entidades foi modelado utilizando a notação EER de Elmasri & Navathe Pelo draw.io.

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
        string papel
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
        string sala
        int vagas
        datetime data_hora_inicio
        datetime data_hora_fim
    }

    INSCRICAO_EVENTO {
        int id_usuario PK, FK
        int id_evento PK, FK
        datetime data_inscricao
        string status
        string comentario_administrador
        string comprovante_usuario BYTEA
        float valor
    }

    PRESENCA_ATIVIDADE {
        int id_usuario PK, FK
        int id_evento PK, FK
        int numero_atividade PK, FK
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
    PRESENCA_ATIVIDADE }o--|| INSCRICAO_EVENTO : "vinculada a"
    ATIVIDADE ||--o{ PRESENCA_ATIVIDADE : "possui"
    USUARIO ||--o{ MINISTRANTE : "ministra"
    ATIVIDADE ||--|{ MINISTRANTE : "Ministrada por"
```

