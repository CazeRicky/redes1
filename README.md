1. Como eu Pensei e Montei o Projeto
Pra esse projeto, a gente tinha que criar um sistema de chat, tipo um WhatsApp simples que roda no computador. A forma que eu pensei pra resolver isso foi a mais clássica que tem na área de redes: uma arquitetura cliente-servidor. Que funciona assim: eu fiz um programa que é o servidor. Ele é o coração do sistema, fica lá ligado o tempo todo, só esperando alguém conectar. E fiz outro programa, que é o 
cliente, que é o que a gente roda no nosso PC pra de fato entrar no chat e conversar.
Na hora de decidir como um programa ia mandar as mensagens pro outro, eu usei o TCP. Eu pensei que, assim como a gente viu no livro do Kurose e Ross, um chat precisa que a conversa seja confiável. Não dá pra uma mensagem chegar pela metade, ou a resposta chegar antes da pergunta, senão vira uma bagunça. O bom de usar o TCP é que ele já resolve tudo isso pra gente, garante que os dados chegam inteiros e na ordem certa, sem eu precisar programar essa parte do zero. Pra fazer essa "ponte" entre o meu código e o TCP, eu usei os 
sockets.

2. As "Regras do Jogo": O Protocolo que eu Criei
Não adiantava só conectar o cliente no servidor. Eles precisavam "falar a mesma língua" pra se entender. Por isso, eu tive que criar o nosso próprio protocolo de aplicação. É como se eu tivesse inventado um conjunto de regras pra conversa: o que significa cada mensagem, qual o formato delas, e quem fala o quê e em qual hora.

Pra organizar essas mensagens, eu usei o formato JSON. É um jeito de escrever que fica bem fácil de ler e de separar as informações. Por exemplo:
Pra mandar uma mensagem: O cliente enviava um pacote tipo {"command": "msg", "from": "remetente", "to": "destinatario", "body": "Oi, tudo bem?"}. O servidor recebia isso, via pra quem era, e mandava pro destinatário certo.
Pra mostrar que alguém tá digitando: Quando a gente começava a escrever, o cliente mandava um aviso pro servidor ("command": "typing", "status": "start"). O servidor repassava esse aviso, e lá na tela do outro usuário aparecia "Fulano está digitando...". Quando parava, mandava outro aviso.
Pra registrar e logar: Tinha também os pacotes pra criar conta e pra entrar no chat, que o servidor usava pra checar no banco de dados se o usuário e a senha estavam certos.

3. Fazendo o Servidor Atender Todo Mundo ao Mesmo Tempo
Um dos maiores problemas a resolver era: como o servidor ia dar conta de várias pessoas conversando ao mesmo tempo? Se eu não fizesse nada, assim que a primeira pessoa conectasse, o servidor ficaria "ocupado" com ela e mais ninguém conseguiria entrar.
A solução pra isso foi usar threads. A ideia é simples: toda vez que um cliente novo se conecta, a thread principal do servidor, que só fica esperando por gente nova, cria uma "thread filha". É como se ela contratasse um atendente novo só pra cuidar daquela conversa. Dessa forma, o servidor fica livre pra aceitar mais gente, enquanto os "atendentes" cuidam das conversas que já estão rolando.
O cliente também usa uma thread pra conseguir receber mensagens a qualquer momento, mesmo enquanto a gente está lá digitando a nossa própria mensagem.

4. O que eu Aprendi com Isso (e o que foi difícil)
Maiores Dificuldades:
Sincronizar tudo no terminal foi um desafio. Como o programa recebe mensagens a qualquer hora, às vezes uma mensagem nova aparecia na tela e "atropelava" o que eu estava digitando. Tive que fazer umas lógicas pra tentar limpar a linha e reescrever, mas ainda não é perfeito.
Outro ponto foi pensar em todos os detalhes do protocolo. A gente acha que é só mandar a mensagem, mas tem que pensar no login, na lista de contatos, no status online/offline, nas mensagens que chegam pra quem tá offline. É bastante coisa pra gerenciar.

Principais Aprendizados:
Ficou muito mais claro como as "camadas" que a gente estuda no livro funcionam na vida real. A minha aplicação (o chat) ficou na camada de aplicação. Eu só precisei me preocupar com as regras do meu protocolo, sem quebrar a cabeça com a entrega dos pacotes. Isso porque eu "contratei" o serviço do TCP, que tá na camada de baixo, pra fazer esse trabalho sujo pra mim.
Deu pra ver na prática por que um servidor precisa ser concorrente. A teoria de que um servidor atende a múltiplos clientes ficou bem real quando eu vi as threads funcionando e consegui abrir várias janelas do cliente, todas conversando entre si, sem o servidor travar.

5. Limitações: O que não deu pra fazer ou poderia ser melhor
Como todo projeto, esse aqui tem umas limitações, e o professor pediu pra gente ser honesto sobre elas.
Interface Gráfica: Eu sei que o projeto pedia uma interface gráfica, com janelas e botões. Mas como o foco da matéria é redes e a gente não viu em aula como fazer GUIs, eu preferi garantir que toda a parte de comunicação, sockets e threads estivesse funcionando 100%. Por isso, fiz o cliente rodar direto no terminal. Ele tem todas as funcionalidades, como ver a lista de contatos e receber mensagens offline, mas não é tão bonito.
Segurança: Essa é a maior limitação. Hoje, segurança é tudo, mas nesse projeto as senhas e as mensagens são enviadas como texto puro, sem nenhuma criptografia. Qualquer um que conseguisse interceptar a comunicação poderia ler tudo. Num sistema de verdade, isso seria um erro gravíssimo.

Mensagens para Offline: Se um usuário envia várias mensagens para alguém que está offline, quando essa pessoa logar, ela vai receber todas as mensagens de uma vez, mas talvez a ordem entre elas não fique perfeita no terminal.
