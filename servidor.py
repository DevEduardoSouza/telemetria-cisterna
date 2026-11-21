#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
servidor.py: CENTRAL DE CONTROLE da cisterna (lado SERVIDOR).

Passo a passo do que acontece:
  1. Pergunta IP, porta e a capacidade total da cisterna (em litros).
  2. Cria um socket TCP, faz bind() no IP/porta e listen(): fica ESCUTANDO.
  3. accept() aceita cada cisterna (cliente) que conecta e cria uma THREAD só
     para ela; assim várias cisternas podem mandar leituras ao mesmo tempo.
  4. Cada leitura vira porcentagem, depois status/alerta, e volta como resposta.
  5. Enquanto isso, o operador digita comandos no terminal: status, ajuda, sair.

Bônus implementados:
  - log_cisterna.txt: histórico com data, hora e volume de cada leitura;
  - alerta de recarga: aumento repentino do volume = captação de água da chuva.

Uso:
    python3 servidor.py                      (pergunta tudo)
    python3 servidor.py --ip 0.0.0.0 --porta 5000 --capacidade 16000
"""

import argparse
import socket
import threading
from datetime import datetime

import comum as c

ARQUIVO_LOG = "log_cisterna.txt"

# Aumento de pelo menos 5% da capacidade entre duas leituras do mesmo ponto
# é considerado chuva (numa cisterna de 16.000 L, isso dá 800 L de uma vez).
LIMIAR_CHUVA = 0.05


# ============================================================================
# REGRA DE NEGÓCIO: transformar litros em nível
# ============================================================================
def classificar(volume, capacidade):
    """Calcula a porcentagem e decide o nível, conforme o enunciado.

        >= 50%       -> NORMAL
        20% a 49,9%  -> MODERADO
        <  20%       -> CRÍTICO

    Devolve (porcentagem, nivel, texto_da_resposta).
    """
    pct = round(volume / capacidade * 100, 1)
    x = c.porcento(pct)
    if pct >= 50:
        return pct, "NORMAL", f"[STATUS: NORMAL ({x}%)]"
    if pct >= 20:
        return pct, "MODERADO", f"[ALERTA: NÍVEL MODERADO ({x}%) - Consumo consciente]"
    return pct, "CRITICO", f"[ALERTA CRÍTICO: NÍVEL BAIXO ({x}%) - Risco de desabastecimento!]"


# ============================================================================
# ESTADO COMPARTILHADO
# ============================================================================
class Central:
    """Guarda as leituras recebidas. É o ESTADO COMPARTILHADO entre as threads.

    Várias threads (uma por cisterna) podem chamar processar_leitura() ao mesmo
    tempo. Sem a trava (Lock), duas threads poderiam alterar o dicionário e o
    arquivo de log juntas e embaralhar os dados (condição de corrida). Com a
    trava, uma thread espera a outra terminar: uma de cada vez.
    """

    def __init__(self, capacidade):
        self.capacidade = capacidade
        self.trava = threading.Lock()
        self.ultima_leitura = None       # última leitura de qualquer ponto
        self.leituras_por_ponto = {}     # "Cisterna_Bloco_A" -> última leitura

    def processar_leitura(self, ponto, volume, endereco):
        pct, nivel, resposta = classificar(volume, self.capacidade)
        leitura = {
            "ponto": ponto,
            "volume": volume,
            "pct": pct,
            "nivel": nivel,
            "quando": datetime.now(),
            "endereco": endereco,
        }

        with self.trava:                          # <- início da região crítica
            anterior = self.leituras_por_ponto.get(ponto)
            aumento = volume - anterior["volume"] if anterior else 0
            choveu = aumento >= LIMIAR_CHUVA * self.capacidade

            self.leituras_por_ponto[ponto] = leitura
            self.ultima_leitura = leitura
            self._gravar_log(leitura, choveu, aumento)
            self._mostrar_no_terminal(leitura, choveu, aumento)
                                                  # <- fim da região crítica
        if choveu:
            resposta = f"[EVENTO: Captação de água pluvial detectada] {resposta}"
        return resposta

    # ---- bônus 1: registro de consumo diário -------------------------------
    def _gravar_log(self, leitura, choveu, aumento):
        quando = leitura["quando"].strftime("%Y-%m-%d %H:%M:%S")
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as log:
            if choveu:
                log.write(f"{quando} | {leitura['ponto']} | EVENTO: Captação de "
                          f"água pluvial detectada (+{c.litros(aumento)})\n")
            log.write(f"{quando} | {leitura['ponto']} | {c.litros(leitura['volume'])} | "
                      f"{c.porcento(leitura['pct'])}% | {leitura['nivel']}\n")

    # ---- saída visual no terminal do servidor ------------------------------
    def _mostrar_no_terminal(self, leitura, choveu, aumento):
        hora = leitura["quando"].strftime("%H:%M:%S")
        cores = {"NORMAL": c.VERDE, "MODERADO": c.AMARELO, "CRITICO": c.VERMELHO}
        linha = (f"[{hora}] {leitura['ponto']} -> {c.litros(leitura['volume'])} "
                 f"({c.porcento(leitura['pct'])}%) {leitura['nivel']}")
        print("\n" + c.cor(linha, cores[leitura["nivel"]]))

        if choveu:      # bônus 2: alerta de recarga
            print(c.cor(f"  [EVENTO: Captação de água pluvial detectada] "
                        f"+{c.litros(aumento)} desde a última leitura", c.CIANO))

        if leitura["nivel"] == "CRITICO":
            # '\a' é o caractere BEL: faz o terminal apitar (aviso sonoro)
            print("\a" + c.cor("=" * 62, c.VERMELHO))
            print(c.cor(f"  !!! ALERTA CRÍTICO: {leitura['ponto']} com "
                        f"{c.porcento(leitura['pct'])}% !!!", c.NEGRITO + c.VERMELHO))
            print(c.cor("  Risco de desabastecimento! Acione o abastecimento por carro-pipa.",
                        c.VERMELHO))
            print(c.cor("=" * 62, c.VERMELHO))

    # ---- comando "status" do painel local ----------------------------------
    def mostrar_status(self):
        with self.trava:
            ultima = self.ultima_leitura
            todas = sorted(self.leituras_por_ponto.values(), key=lambda l: l["ponto"])

        print(c.cor("\n------------------ PAINEL DA CENTRAL ------------------", c.NEGRITO))
        print(f"Capacidade configurada: {c.litros(self.capacidade)}")
        if ultima is None:
            print("Nenhuma leitura recebida ainda.")
            return
        print(c.cor("Última leitura recebida:", c.NEGRITO))
        print(f"  Ponto de medição : {ultima['ponto']}  ({ultima['endereco']})")
        print(f"  Volume           : {c.litros(ultima['volume'])}")
        print(f"  Nível            : {c.porcento(ultima['pct'])}%  {ultima['nivel']}")
        print(f"  Data/hora        : {ultima['quando'].strftime('%d/%m/%Y %H:%M:%S')}")
        if len(todas) > 1:
            print(c.cor("Última leitura de cada ponto:", c.NEGRITO))
            for l in todas:
                print(f"  {l['ponto']:<22} {c.litros(l['volume']):>10}  "
                      f"{c.porcento(l['pct']):>5}%  {l['nivel']:<9} "
                      f"{l['quando'].strftime('%H:%M:%S')}")
        print("-" * 55)


# ============================================================================
# COMUNICAÇÃO: uma thread por cliente
# ============================================================================
def atender_cliente(conexao, endereco, central):
    """Conversa com UMA cisterna até ela mandar SAIR ou a conexão cair."""
    endereco_txt = f"{endereco[0]}:{endereco[1]}"
    ponto = endereco_txt        # até o cliente se identificar com ID
    print(c.cor(f"\n[+] Conexão TCP aceita de {endereco_txt}", c.CINZA))

    try:
        with conexao, c.leitor(conexao) as entrada:
            while True:
                mensagem = c.receber(entrada)
                if mensagem is None:            # cliente fechou sem avisar
                    break

                # "LEITURA 12000" -> comando="LEITURA", argumento="12000"
                comando, _, argumento = mensagem.partition(" ")
                comando = comando.upper()

                if comando == c.CMD_ID:
                    ponto = argumento.strip() or endereco_txt
                    print(c.cor(f"[+] {endereco_txt} identificado como '{ponto}'", c.CINZA))
                    c.enviar(conexao, f"{c.RESP_OK} {central.capacidade}")

                elif comando == c.CMD_LEITURA:
                    c.enviar(conexao, validar_e_processar(argumento, ponto,
                                                          endereco_txt, central))

                elif comando == c.CMD_SAIR:
                    c.enviar(conexao, c.RESP_TCHAU)
                    break

                else:
                    c.enviar(conexao, f"[ERRO: comando desconhecido '{comando}']")
    except OSError:                             # conexão resetada, rede caiu...
        pass
    print(c.cor(f"\n[-] {ponto} ({endereco_txt}) desconectou", c.CINZA))


def validar_e_processar(argumento, ponto, endereco_txt, central):
    """Valida o volume recebido antes de analisar. Devolve a resposta."""
    try:
        volume = float(argumento.strip().replace(",", "."))
    except ValueError:
        return f"[ERRO: volume inválido '{argumento}'. Envie um número em litros]"
    if volume < 0:
        return "[ERRO: volume não pode ser negativo]"
    if volume > central.capacidade:
        return (f"[ERRO: volume acima da capacidade da cisterna "
                f"({c.litros(central.capacidade)})]")
    return central.processar_leitura(ponto, volume, endereco_txt)


def aceitar_conexoes(servidor, central):
    """Laço do accept(): roda numa thread separada para não travar o teclado."""
    while True:
        try:
            conexao, endereco = servidor.accept()   # bloqueia até alguém conectar
        except OSError:                             # socket fechado no 'sair'
            break
        threading.Thread(target=atender_cliente, args=(conexao, endereco, central),
                         daemon=True).start()


# ============================================================================
# PROGRAMA PRINCIPAL
# ============================================================================
AJUDA = """Comandos da central:
  status  - mostra a última leitura recebida e a data/hora do registro
  ajuda   - mostra esta lista
  sair    - desliga a central"""


def main():
    parser = argparse.ArgumentParser(description="Central de telemetria da cisterna")
    parser.add_argument("--ip")
    parser.add_argument("--porta", type=int)
    parser.add_argument("--capacidade", type=int, help="capacidade total em litros")
    args = parser.parse_args()

    print(c.cor("=== CENTRAL DE CONTROLE: TELEMETRIA DE CISTERNA (Irecê/BA) ===", c.NEGRITO))
    ip = args.ip or c.perguntar("IP para escutar (0.0.0.0 = todas as placas de rede)",
                                "0.0.0.0")
    porta = args.porta or c.perguntar_numero("Porta", c.PORTA_PADRAO, 1024, 65535)
    capacidade = args.capacidade or c.perguntar_numero(
        "Capacidade total da cisterna (litros)", 16000, 1)

    # AF_INET = IPv4, SOCK_STREAM = TCP
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Permite reabrir a mesma porta logo após fechar o servidor
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        servidor.bind((ip, porta))
    except OSError as erro:
        print(c.cor(f"Não foi possível usar {ip}:{porta}: {erro}", c.VERMELHO))
        return 1
    servidor.listen()

    central = Central(capacidade)
    print(c.cor(f"\nCentral escutando em {ip}:{porta}  |  capacidade "
                f"{c.litros(capacidade)}  |  log em {ARQUIVO_LOG}", c.VERDE))
    print(AJUDA + "\n")

    aceitador = threading.Thread(target=aceitar_conexoes, args=(servidor, central),
                                 daemon=True)
    aceitador.start()

    # Painel local: o teclado do servidor fica livre para comandos
    try:
        while True:
            comando = input("central> ").strip().lower()
            if comando == "status":
                central.mostrar_status()
            elif comando in ("ajuda", "help", "?"):
                print(AJUDA)
            elif comando == "sair":
                break
            elif comando:
                print("Comando desconhecido. Digite 'ajuda'.")
    except EOFError:            # sem teclado (rodando em segundo plano)
        aceitador.join()
    except KeyboardInterrupt:   # Ctrl+C
        print()

    print("Desligando a central...")
    servidor.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
