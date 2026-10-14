# Regras de Negócio

## Usuário

- O cpf e email são únicos para cada usuário
- Usuários conseguem ver em quais eventos eles estão inscritos em `/user/events`, essa listagem deve mostrar uma prévia das inscrições pendentes também. Uma página de detalhes em `/user/events/{id}/attendances` deve mostrar quais atividades o usuário esteve presente.
- Para acessar o sistema o usuário deve estar autenticado, após seguir o fluxo de login e senha em `/login`

## Eventos

- Um evento precisa ter pelo menos uma atividade 
- A lista de todos os eventos é mostrada na página `/events`, os eventos devem ser mostrados como cards e um evento sem vagas deve aparecer desabilitado com um tooltip informativo (mas usuários administradores ainda conseguem ver os detalhes)
- Em `/events`, um usuário administrador pode interagir com um botão 'Criar evento' que abre um dialog para adicionar um novo evento
- Adminstradores conseguem ver detalhes de um evento específico com o valor arrecadado pelas inscrições confirmadas, quanto vai ser arrecadado com as inscrições pendentes e quanto foi deixado de arrecadar nas inscrições canceladas, esse detalhamento deve ser mostrado de forma tabular na página `/events/{id}`
- Administradores conseguem ver quais inscrições estão pendentes em `/events/{id}/registrations`. Em `/events/{id}/registrations/{id}` o administrador pode fazer comentários, aceitar ou recusar a inscrição.

### Inscrição 

- Usuários podem se inscrever por um botão na página `/events/{id}`. Que abre um dialog para informar os dados de inscrição
- A inscrição de um usuário inicia como pendente e deve ser confirmada por um administrador. O usuário informa o valor e anexa um comprovante, o administrador também pode adicionar um comentário após avaliar 
- O usuário pode editar uma inscrição pendente em `/user/registrations/{id}`
- Usuários só podem se inscrever no evento se a idade deles estiver adequada à classificação indicativa 
- O usuário que solicitou a inscrição pode cancelar uma inscrição pendente ou confirmada, é necessário pedir por confirmação do usuário antes de concluir o cancelamento. Essa opção está disponível em `/user/registrations/{id}`
- Só podem haver inscrições até o número de vagas do evento ser atingido

### Atividades

- Criar uma atividade deve ser feito por meio de um botão que abre um dialog na página `/events/{id}/activities`
- A listagem de atividades de um evento fica em `/events/{id}/activities/{id}`
- Uma atividade deve possuir pelo menos um ministrante. Os detalhes de uma atividade ficam em `/events/{id}/activities/{id}` e nessa página um administrador pode editar ministrantes e outros detalhes da atividade
- O horário da atividade deve estar contido no horário do evento
- Os participantes de uma atividade devem estar inscritos no evento a que a atividade pertence

#### Presença atividade

- Um usuário administrador é responsável por adicionar a presença durante ou após a atividade. Em `/events/{id}/activities/{id}`. A lista dos usuários que podem receber a presença só é mostrada ao administrador

