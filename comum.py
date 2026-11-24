# -*- coding: utf-8 -*-
"""
comum.py: código usado TANTO pelo cliente QUANTO pelo servidor.

Aqui fica o PROTOCOLO, o "idioma" que os dois lados combinaram para conversar
pela rede, e algumas utilidades de terminal (cores, perguntas, formatação).

------------------------------------------------------------------------------
POR QUE MENSAGENS EM LINHAS?
------------------------------------------------------------------------------
O TCP entrega um FLUXO CONTÍNUO de bytes, não "mensagens". Se o cliente manda
"LEITURA 100" e logo depois "LEITURA 90", o servidor pode receber tudo junto
("LEITURA 100LEITURA 90") ou picado ("LEIT" + "URA 100..."). Por isso foi
combinado:

    >>> cada mensagem é UMA linha de texto UTF-8 terminada em '\n' <<<

Assim o receptor lê até o '\n' e sabe exatamente onde a mensagem termina.

------------------------------------------------------------------------------
MENSAGENS DO PROTOCOLO
------------------------------------------------------------------------------
    Cliente (cisterna)  ->  Servidor (central)
        ID <ponto>            identifica o ponto de medição (1ª mensagem)
        LEITURA <litros>      envia o volume medido
        SAIR                  encerra a conexão

    Servidor (central)  ->  Cliente (cisterna)
        OK <capacidade>       resposta ao ID (informa a capacidade em litros)
        [STATUS: ...]         resposta a uma LEITURA (nível normal)
        [ALERTA: ...]         resposta a uma LEITURA (nível moderado)
        [ALERTA CRÍTICO: ...] resposta a uma LEITURA (nível baixo)
        [EVENTO: ...] [...]   evento de chuva + status, na mesma linha
        [ERRO: ...]           pedido inválido
        TCHAU                 confirma o SAIR

Regra de ouro: para CADA pedido do cliente, o servidor manda EXATAMENTE UMA
linha de resposta (modelo pedido/resposta).
"""

import os

# ----------------------------------------------------------------------------
# Constantes do protocolo
# ----------------------------------------------------------------------------
# Ficam num único lugar para cliente e servidor usarem EXATAMENTE as mesmas
# palavras. Se um lado escrevesse "LEITURA" e o outro esperasse "Leitura",
# a conversa falharia. Mudou o protocolo? Muda só aqui.
CODIFICACAO = "utf-8"       # como converter texto <-> bytes (a rede só leva bytes)
PORTA_PADRAO = 5000         # porta TCP sugerida; acima de 1023 não exige root

CMD_ID = "ID"               # comandos que o CLIENTE envia
CMD_LEITURA = "LEITURA"
CMD_SAIR = "SAIR"

RESP_OK = "OK"              # respostas curtas do SERVIDOR
RESP_TCHAU = "TCHAU"


def enviar(sock, texto):
    """Envia uma mensagem (uma linha) pelo socket.

    Passo a passo:
      1. acrescenta o '\n' que marca o FIM da mensagem;
      2. converte o texto em bytes (encode), porque a rede só transporta bytes;
      3. sendall() garante que TODOS os bytes saiam. O send() comum pode
         mandar só uma parte e devolver quantos bytes conseguiu enviar.
    """
    sock.sendall((texto + "\n").encode(CODIFICACAO))


def leitor(sock):
    """Cria um "arquivo" de leitura em cima do socket.

    makefile() devolve um objeto que se comporta como um arquivo aberto.
    Com ele, readline() vai acumulando os pedaços que chegam pela rede
    (chamando recv() por baixo dos panos) até encontrar o '\n'; só então
    devolve a linha. Ou seja: devolve sempre UMA mensagem inteira, nem mais,
    nem menos, mesmo que o TCP tenha picado ou juntado os bytes no caminho.
    """
    return sock.makefile("r", encoding=CODIFICACAO)


def receber(arquivo):
    """Lê a próxima mensagem. Devolve None se o outro lado fechou a conexão.

    readline() é BLOQUEANTE: a thread fica parada aqui até chegar uma linha
    completa. Quando o outro lado fecha o socket, o TCP sinaliza fim de fluxo
    (EOF) e readline() devolve string vazia; é assim que descobrimos que a
    conexão acabou.
    """
    linha = arquivo.readline()
    if not linha:           # string vazia = conexão encerrada (EOF)
        return None
    return linha.rstrip("\r\n")     # tira o '\n' do fim (e o '\r', se vier)


# ----------------------------------------------------------------------------
# Utilidades de terminal
# ----------------------------------------------------------------------------
# Nada daqui passa pela rede; serve só para a tela ficar legível.
if os.name == "nt":         # no Windows, ativa as cores ANSI do terminal
    os.system("")

# Códigos de escape ANSI: o terminal interpreta "\033[91m" como a ordem
# "mude a cor para vermelho" em vez de mostrar esses caracteres.
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
VERDE = "\033[92m"
CIANO = "\033[96m"
CINZA = "\033[90m"
NEGRITO = "\033[1m"
RESET = "\033[0m"           # volta à cor normal


def cor(texto, codigo):
    """Envolve o texto com o código de cor e o RESET no fim: 'cor + texto + normal'."""
    return f"{codigo}{texto}{RESET}"


def litros(valor):
    """12000 -> '12.000 L' (separador de milhar brasileiro)."""
    return f"{valor:,.0f}".replace(",", ".") + " L"


def porcento(valor):
    """62.5 -> '62,5' (vírgula decimal brasileira)."""
    return f"{valor:.1f}".replace(".", ",")


def perguntar(texto, padrao):
    """Pergunta algo no terminal; ENTER vazio aceita o valor padrão."""
    resposta = input(f"{texto} [{padrao}]: ").strip()
    return resposta or str(padrao)


def perguntar_numero(texto, padrao, minimo=1, maximo=None, inteiro=True):
    """Pergunta um número e repete até o usuário digitar um valor válido.

    Aceita o jeito brasileiro de escrever: "16.000" vira 16000 e "2,5" vira 2.5.
    """
    while True:
        bruto = perguntar(texto, padrao)
        if inteiro:
            bruto = bruto.replace(".", "")      # aceita "16.000" como 16000
        bruto = bruto.replace(",", ".")         # vírgula decimal -> ponto (padrão do Python)
        try:
            valor = int(bruto) if inteiro else float(bruto)
        except ValueError:                      # digitou letras, por exemplo
            print(cor("  Valor inválido, digite só números.", VERMELHO))
            continue
        if valor < minimo or (maximo is not None and valor > maximo):
            limite = f"entre {minimo} e {maximo}" if maximo else f"a partir de {minimo}"
            print(cor(f"  Valor fora do intervalo ({limite}).", VERMELHO))
            continue
        return valor
