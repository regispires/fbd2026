# Regras de Negócio

## Usuário

- O cpf e email são únicos para cada usuário
- Usuários conseguem ver em quais eventos eles estão inscritos em `/user/events`, essa listagem deve mostrar uma prévia das inscrições pendentes também. Uma página de detalhes em `/user/events/{id}/attendances` deve mostrar quais atividades o usuário esteve presente.
- Para acessar o sistema o usuário deve estar autenticado, após seguir o fluxo de login e senha em `/login`

## Eventos

- Um evento precisa ter pelo menos uma atividade 
- A lista de todos os eventos é mostrada na página `/`, os eventos devem ser mostrados como cards e um evento sem vagas deve aparecer desabilitado com um tooltip informativo (mas usuários administradores ainda conseguem ver os detalhes)
- Em `/`, um usuário administrador pode interagir com um botão 'Criar evento' que abre um dialog para adicionar um novo evento
- Adminstradores conseguem ver detalhes de um evento específico com o valor arrecadado pelas inscrições confirmadas, quanto vai ser arrecadado com as inscrições pendentes e quanto foi deixado de arrecadar nas inscrições canceladas, esse detalhamento deve ser mostrado de forma tabular na página `/event/{id}`
- Administradores conseguem ver quais inscrições estão pendentes em `/event/{id}/registrations`. Em `/event/{id}/registrations/{id}` o administrador pode fazer comentários, aceitar ou recusar a inscrição. O comentário pode ser salvo independentemente de aprovar ou recusar

### Inscrição 

- Usuários podem se inscrever por um botão na página `/event/{id}`. Que abre um dialog para informar os dados de inscrição. Após finalizar a inscrição, o usuário é direcionado para a página de detalhes das inscrições dele
- O evento possui um preço (valor cheio) definido; o usuário escolhe pagar o valor cheio ou a meia-entrada (metade do valor) e anexa um comprovante — na meia-entrada, o comprovante também justifica o pedido de desconto. O valor da inscrição é derivado do preço do evento, o usuário não informa o valor manualmente
- A inscrição de um usuário inicia como pendente e deve ser confirmada por um administrador, que pode aprovar, recusar ou apenas comentar a inscrição. Administradores não podem aprovar nem recusar a própria inscrição
- O usuário pode editar uma inscrição pendente (meia-entrada e comprovante) em `/user/registrations/{id}`
- Usuários só podem se inscrever no evento se a idade deles estiver adequada à classificação indicativa 
- O usuário que solicitou a inscrição pode cancelar uma inscrição pendente ou confirmada, é necessário pedir por confirmação do usuário antes de concluir o cancelamento. Essa opção está disponível em `/user/registrations/{id}`
- Só podem haver inscrições até o número de vagas do evento ser atingido

### Atividades

- Criar uma atividade deve ser feito por meio de um botão que abre um dialog na página `/event/{id}/activities`
- A listagem de atividades de um evento fica em `/event/{id}/activities/{id}`
- Uma atividade deve possuir pelo menos um ministrante. Os detalhes de uma atividade ficam em `/event/{id}/activities/{id}` e nessa página um administrador pode editar ministrantes e outros detalhes da atividade
- O horário da atividade deve estar contido no horário do evento
- Os participantes de uma atividade devem estar inscritos no evento a que a atividade pertence

#### Presença atividade

- Um usuário administrador é responsável por adicionar a presença durante ou após a atividade. Em `/events/{id}/activities/{id}`. A lista dos usuários que podem receber a presença só é mostrada ao administrador

