# Regras de Negócio

## Usuário

- O cpf e email são únicos para cada usuário

## Eventos

- Um evento precisa ter pelo menos uma atividade 
- Usuários só podem se inscrever no evento se a idade deles estiver adequada à classificação indicativa 

### Inscrição 

- A inscrição de um usuário inicia como pendente e deve ser confirmada por ele em um segundo momento
- Um usuário pode cancelar uma inscrição pendente ou confirmada
- Cancelar uma inscrição deve cancelar a inscrição do usuário em todas as atividades do evento
- Só podem haver inscrições até o número de vagas do evento ser atingido
- Um usuário admin é responsável por adicionar a presença durante ou após a atividade 

### Atividades

- Uma atividade deve possuir pelo menos um ministrante
- O horário da atividade deve estar contido no horário do evento
- Os participantes de uma atividade devem estar inscritos no evento a que a atividade pertence

#### Inscrição Atividade 

- O usuário só pode se inscrever em atividades após confirmar a inscrição no evento
- A inscrição de um usuário inicia como pendente e deve ser confirmada por ele em um segundo momento
- Um usuário pode cancelar uma inscrição pendente ou confirmada
- Só podem haver inscrições até o número de vagas da atividade ser atingido
- Um usuário admin é responsável por adicionar a presença durante ou após a atividade 
