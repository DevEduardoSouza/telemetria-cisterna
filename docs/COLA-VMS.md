# COLA · Fase 1: VMs e rede · 2 min · vale até 2,0

Abra no celular ou imprima. Só o que precisa ser **digitado** está aqui; o resto o `ambiente.sh`
imprime na tela (Debian, hostname, IPs, ping e sockets TCP da porta 5000).

---

## ANTES (10 min antes da aula)

- [ ] Ligar as **2 VMs** (servidor e cliente)
- [ ] Nas duas: `cd telemetria-cisterna && git pull`
- [ ] Na VM **cliente**: `bash ambiente.sh` → tem que aparecer **✔ As VMs se enxergam**
- [ ] Deu ✘? Restaurar o snapshot `pronto-apresentacao` nas duas VMs e repetir
- [ ] Servidor: `rm -f log_cisterna.txt`
- [ ] Cliente: abrir **2 terminais**. Servidor: abrir **2 terminais**
- [ ] Som da VM do servidor ligado (apito do alerta crítico)

---

## NA HORA (nesta ordem)

| # | Onde | Faço | Falo |
|---|---|---|---|
| 1 | VirtualBox | Mostrar as **2 VMs**. Em uma: Configurações → Rede → Adaptador 2 | "Duas VMs Debian independentes, numa rede interna só delas, a `intnet`." |
| 2 | VM **servidor** | `bash ambiente.sh` | "Servidor: Debian 12, IP terminado em .10." |
| 3 | VM **cliente** | `bash ambiente.sh` | "Cliente: Debian 12, IP .20. O ping prova que as duas se enxergam." |
| 4 | VM **servidor** | `python3 servidor.py --ip 0.0.0.0 --porta 5000 --capacidade 16000` | "0.0.0.0: aceita conexão por qualquer placa, inclusive a da outra VM." |
| 5 | VM **cliente** | `python3 cliente.py --ip 192.168.50.10 --porta 5000 --ponto Cisterna_Bloco_A` | "O cliente conectou vindo de outra máquina." |
| 6 | VM **servidor**, 2º terminal | `bash ambiente.sh` | "O kernel mostra a conexão TCP estabelecida: .10:5000 de um lado, .20 do outro." |

Depois do passo 6 → **Fase 2: demonstração** (roteiro, seção 3). O servidor e o cliente já estão
no ar; é só escolher a opção `1` no cliente.

---

## SE DER ERRADO

| Vejo | Faço |
|---|---|
| ✘ Sem resposta no ping | `ip link` mostra `enp0s8`? → `sudo ifup enp0s8`. Não resolveu → snapshot |
| `Connection refused` no cliente | Servidor não está rodando. Volte ao passo 4 |
| Cliente conecta só na própria VM | Servidor em `127.0.0.1`. Suba de novo com `--ip 0.0.0.0` |
| `Address already in use` | Servidor antigo aberto em outro terminal. Feche-o (Ctrl+C) |
| Nenhum socket na porta 5000 | Servidor ainda não subiu, ou subiu em outra porta |

---

## FRASES DE SEGURANÇA

**"Por que TCP e não UDP?"**
> "Uma leitura de nível não pode se perder nem chegar fora de ordem. O TCP garante entrega, ordem e
> conexão. Um alerta crítico perdido seria um problema real."

**"Por que 0.0.0.0?"**
> "Escuta em todas as placas da VM. Com 127.0.0.1 só aceitaria conexão da própria máquina."

**"Como sei que são máquinas diferentes?"**
> "Hostnames diferentes, IPs diferentes e o `ss` mostra a conexão entre os dois IPs."
