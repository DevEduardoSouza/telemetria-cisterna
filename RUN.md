# RUN · Checklist da Projeto

Login nas VMs: usuário `eduardo` (senha combinada).

---

- [x] **[Até 2,0] Uso de VMs / Ambientes Distintos**
  Configuração correta de rede e execução em instâncias isoladas (Debian/VirtualBox).

### Passo a passo

1. Abrir o **VirtualBox**. Na lista aparecem `debian-servidor` e `debian-cliente`.
2. **Iniciar as duas** (selecionar → Iniciar). Elas sobem direto no terminal, em 30 a 40 s.

   Coloque as duas janelas lado a lado.
3. Entrar nas duas com o usuário `eduardo`.
4. Nas duas:
   ```bash
     cd telemetria-cisterna
     bash ambiente.sh
   ```
5. Mostrar, apontando na tela:
   - VirtualBox com as **duas VMs** (Configurações → Rede → Adaptador 2 = Rede Interna `intnet`);
   - em cada VM: `Debian GNU/Linux 12`, hostname `servidor` / `cliente`;
   - IPs diferentes na mesma rede: `192.168.50.10` e `192.168.50.20` na `enp0s8`;
   - `[OK] As VMs se enxergam` (ping entre elas).

### Se der errado

| Vejo | Faço |
|---|---|
| `[X] Sem resposta` no ping | Esperar a outra VM terminar de subir e rodar `bash ambiente.sh` de novo |
| VM travada ou com mensagens de `soft lockup` | O notebook dormiu. Máquina → Reinicializar (volta em 40 s) |
| Nada do que digito aparece | Clicar dentro da janela da VM certa |
| `Address already in use` ao subir o servidor | O servidor já está rodando em outro console (`Alt+F1`...`Alt+F6` para achar). Ou `pkill -f servidor.py` e subir de novo |
| Tudo errado | VirtualBox → VM → Snapshots → `pronto-apresentacao` → Restaurar (nas duas) |

### Dicas

- **Comandos prontos:** aperte a **seta para cima** (↑) no terminal da VM e os comandos da apresentação aparecem inteiros; é só dar Enter. `Ctrl+R` e digitar parte do comando também busca.
- **Segundo terminal** na mesma VM: `Alt+F2` abre outro console (entre de novo com `eduardo`). `Alt+F1` volta.
- O mouse fica sempre livre; para digitar numa VM, clique nela.
- Não deixe o notebook dormir nem feche a tampa com as VMs ligadas.
- **Para fechar a VM:** feche a janela (ela desliga sozinha, de forma limpa) ou digite `sudo poweroff`. Nunca use "Salvar o estado": a VM voltaria com o servidor antigo ainda rodando.
- Guia rápido desta fase: [`docs/COLA-VMS.md`](docs/COLA-VMS.md).

---

- [ ] **[Até 3,0] Requisitos Funcionais (Servidor e Cliente)**
  Implementação completa do protocolo, comandos, fluxos e validações obrigatórias.

1. VM servidor: `python3 servidor.py --ip 0.0.0.0 --porta 5000 --capacidade 16000`
2. VM cliente: `python3 cliente.py --ip 192.168.50.10 --porta 5000 --ponto Cisterna_Bloco_A`
3. Modo manual (`1`): `12000` → NORMAL · `6000` → MODERADO · `2500` → CRÍTICO (apito no servidor) · `abc` e `99999` → validações.
4. Segundo console no cliente (`Alt+F2`): `python3 cliente.py --ip 192.168.50.10 --porta 5000 --ponto Cisterna_Bloco_B`, opção `2`, volume `9000`, consumo `1000`, depois `chuva 4000`.
5. Servidor: `status`. Em outro console do servidor: `bash ambiente.sh` (mostra as conexões `ESTABELECIDA`) e `cat log_cisterna.txt`.
6. Cliente: `sair`. No servidor aparece `desconectou`.

Roteiro detalhado: [`docs/ROTEIRO-APRESENTACAO.md`](docs/ROTEIRO-APRESENTACAO.md), seção 3.

---

- [ ] **[Até 3,0] Apresentação Prática**
  Demonstração do sistema em funcionamento, explicação do código e domínio do tema.

1. Explicar o código na ordem: `comum.py` (protocolo em linhas) → `servidor.py` (`main`, `atender_cliente`, `classificar`, `Central` + `Lock`) → `cliente.py` (`Simulacao.rodar`).
2. Perguntas prováveis e respostas: roteiro, seção 6.

---

- [ ] **[Até 2,0] Recursos Opcionais (Bônus)**
  Implementação dos requisitos avançados/opcionais indicados na atividade.

1. `cat log_cisterna.txt` no servidor (registro diário com data, hora, volume, % e nível).
2. Evento `[EVENTO: Captação de água pluvial detectada]` com o `chuva 4000` do passo anterior.
3. Mostrar o histórico de commits no GitHub.
