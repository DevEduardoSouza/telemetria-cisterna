#!/usr/bin/env bash
# ambiente.sh - mostra, de forma visual, o ambiente desta VM para a apresentação.
#
# Uso:  bash ambiente.sh [IP_DA_OUTRA_VM] [PORTA]
# Sem argumentos: descobre a outra VM pelo padrão do README (192.168.50.10 <-> .20)
# e usa a porta 5000. Rode ANTES e DEPOIS de subir servidor/cliente.

PORTA="${2:-5000}"

# cores (só se a saída for um terminal)
if [ -t 1 ]; then
  N=$'\e[0m'; B=$'\e[1m'; VERDE=$'\e[32m'; VERM=$'\e[31m'; AMAR=$'\e[33m'; AZUL=$'\e[36m'
else
  N=""; B=""; VERDE=""; VERM=""; AMAR=""; AZUL=""
fi

L1="════════════════════════════════════════════════════════════"
L2="────────────────────────────────────────────────────────────"
titulo() { printf '%s\n%s  %s%s\n%s\n' "$L1" "$B$AZUL" "$1" "$N" "$L1"; }

HOST=$(hostname)
SO=$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")
PY=$(python3 --version 2>&1)

# IPv4 de todas as placas, menos a loopback
IPS=$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $2, $4}')
MEU_IP=$(printf '%s\n' "$IPS" | awk '{print $2}' | cut -d/ -f1 | grep '^192\.168\.50\.' | head -n1)

if [ -n "$1" ]; then
  OUTRO="$1"
elif [ "$MEU_IP" = "192.168.50.10" ]; then
  OUTRO="192.168.50.20"
else
  OUTRO="192.168.50.10"
fi

clear
titulo "AMBIENTE DA VM: $HOST"
printf ' %-9s %s\n' "Sistema:"  "${SO:-desconhecido}"
printf ' %-9s %s\n' "Hostname:" "$HOST"
printf ' %-9s %s\n' "Python:"   "$PY"
printf ' Placas de rede (IPv4):\n'
if [ -n "$IPS" ]; then
  printf '%s\n' "$IPS" | while read -r placa ip; do
    if [ "${ip%/*}" = "$MEU_IP" ]; then
      printf '    %-8s %s%s%s   <- rede interna do projeto\n' "$placa" "$B" "$ip" "$N"
    else
      printf '    %-8s %s\n' "$placa" "$ip"
    fi
  done
else
  printf '    %snenhum IP configurado%s\n' "$VERM" "$N"
fi

printf '%s\n' "$L2"
printf ' Ping para a outra VM (%s)...\n' "$OUTRO"
SAIDA_PING=$(ping -c 3 -W 1 "$OUTRO" 2>&1)
if [ $? -eq 0 ]; then
  RTT=$(printf '%s\n' "$SAIDA_PING" | grep -o 'time=[0-9.]* ms' | tail -n1)
  printf '    %s✔ As VMs se enxergam%s   (3 enviados, 3 recebidos, %s)\n' "$VERDE$B" "$N" "${RTT:-ok}"
else
  printf '    %s✘ Sem resposta de %s%s   -> conferir Rede Interna e IP fixo\n' "$VERM$B" "$OUTRO" "$N"
fi

printf '%s\n' "$L2"
printf ' Sockets TCP na porta %s (comando: ss -tan):\n' "$PORTA"
SOCK=$(ss -Htan "( sport = :$PORTA or dport = :$PORTA )" 2>/dev/null)
if [ -n "$SOCK" ]; then
  printf '%s\n' "$SOCK" | awk -v v="$VERDE$B" -v a="$AMAR$B" -v n="$N" '
    $1=="LISTEN" { printf "    %sLISTEN%s        %-22s (servidor escutando)\n", v, n, $4 }
    $1=="ESTAB"  { printf "    %sESTABELECIDA%s  %-22s <->  %s\n", a, n, $4, $5 }
    $1!="LISTEN" && $1!="ESTAB" { printf "    %-13s %-22s <->  %s\n", $1, $4, $5 }'
else
  printf '    (nenhum ainda: suba o servidor e o cliente e rode este script de novo)\n'
fi
printf '%s\n' "$L1"
