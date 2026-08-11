#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construtor do catálogo completo — roda no GitHub Actions (na nuvem).

Baixa a base pública da ANVISA (Dados Abertos — medicamentos registrados),
monta um catálogo compacto com TODOS os produtos e mescla os dados clínicos
CURADOS (indicações, contraindicações, alertas, posologia, tarja) do
medicamentos.json por princípio ativo.

Saída: catalogo.json (na raiz do site). NÃO roda na máquina do usuário —
executa no runner do GitHub. Fonte oficial:
https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv
"""
import csv
import html
import io
import json
import os
import re
import ssl
import sys
import unicodedata
import urllib.request

URL_ANVISA = os.environ.get("URL_ANVISA", "https://dados.anvisa.gov.br/dados/DADOS_ABERTOS_MEDICAMENTOS.csv")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # pasta do site
CURADO = os.path.join(BASE, "medicamentos.json")
SAIDA = os.path.join(BASE, "catalogo.json")

# Limite de segurança para não gerar um JSON gigante demais para o navegador.
MAX_ITENS = int(os.environ.get("MAX_ITENS", "40000"))


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def achar_col(cabecalho, *chaves):
    up = {norm(c): c for c in cabecalho}
    for k in chaves:
        nk = norm(k)
        for chave_norm, original in up.items():
            if nk == chave_norm or nk in chave_norm:
                return original
    return None


def baixar_csv(url):
    print(f"Baixando {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (farmacia-brasil-bot)"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read()
    except (ssl.SSLError, urllib.error.URLError) as e:
        # Servidores gov.br frequentemente não enviam a cadeia intermediária do
        # certificado; para uma base PÚBLICA, seguimos sem verificar o certificado.
        print(f"  Aviso SSL ({e}); repetindo sem verificação de certificado.")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=300, context=ctx) as r:
            raw = r.read()
    print(f"  {len(raw)/1_000_000:.1f} MB baixados")
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def main():
    texto = baixar_csv(URL_ANVISA)
    amostra = texto[:5000]
    delim = ";" if amostra.count(";") >= amostra.count(",") else ","
    rd = csv.DictReader(io.StringIO(texto), delimiter=delim)
    cab = rd.fieldnames or []
    print("Colunas detectadas:", cab)

    c_prod = achar_col(cab, "NOME_PRODUTO", "PRODUTO", "NOME_COMERCIAL")
    c_princ = achar_col(cab, "PRINCIPIO_ATIVO", "SUBSTANCIA", "PRINCIPIOATIVO")
    c_emp = achar_col(cab, "NOME_EMPRESA", "EMPRESA", "RAZAO_SOCIAL", "EMPRESA_DETENTORA")
    c_classe = achar_col(cab, "CLASSE_TERAPEUTICA", "CATEGORIA_REGULATORIA", "CLASSE")
    c_sit = achar_col(cab, "SITUACAO_REGISTRO", "SITUACAO")
    c_tipo = achar_col(cab, "CATEGORIA_REGULATORIA", "TIPO_PRODUTO", "TIPO")

    print("Mapeamento:", {"produto": c_prod, "principio": c_princ, "empresa": c_emp,
                          "classe": c_classe, "situacao": c_sit, "tipo": c_tipo})

    vistos = set()
    itens = []
    total = 0
    for row in rd:
        total += 1
        if c_sit:
            sit = norm(row.get(c_sit) or "")
            # SITUACAO_REGISTRO = "Ativo"/"Inativo"; mantém só os ativos
            if sit and sit != "ativo" and "valid" not in sit:
                continue
        princ = re.sub(r"^[\s\-/.,;+]+", "", html.unescape((row.get(c_princ) or "")).strip()) if c_princ else ""
        prod = re.sub(r"^[\s\-/.,;+]+", "", html.unescape((row.get(c_prod) or "")).strip()) if c_prod else ""
        nome = princ or prod
        if not nome:
            continue
        chave = (norm(prod), norm(princ))
        if chave in vistos:
            continue
        vistos.add(chave)
        itens.append({
            "principio": (princ or prod).title(),
            "produto": prod.title(),
            "classe": html.unescape((row.get(c_classe) or "")).strip().title() if c_classe else "",
            "empresa": html.unescape((row.get(c_emp) or "")).strip().title() if c_emp else "",
            "tipo": html.unescape((row.get(c_tipo) or "")).strip().lower() if c_tipo else "",
            "tarja": "A confirmar",
            "grupo": norm(princ or prod),
            "ean": None, "preco": None,
            "indicacoes": [], "contraindicacoes": [], "alertas": [], "enfermidades": [],
            "posologia": "", "origem": "ANVISA",
        })
        if len(itens) >= MAX_ITENS:
            print(f"  Limite de {MAX_ITENS} itens atingido.")
            break
    print(f"Linhas lidas: {total} · produtos únicos válidos: {len(itens)}")

    # Mescla dados clínicos curados por grupo (princípio ativo normalizado)
    curados = json.load(open(CURADO, encoding="utf-8"))["medicamentos"]
    por_grupo = {}
    for c in curados:
        por_grupo.setdefault(c.get("grupo") or norm(c["principio"]), c)

    enriquecidos = 0
    grupos_no_catalogo = set()
    for it in itens:
        grupos_no_catalogo.add(it["grupo"])
        c = por_grupo.get(it["grupo"])
        if c:
            it["indicacoes"] = c.get("indicacoes", [])
            it["contraindicacoes"] = c.get("contraindicacoes", [])
            it["alertas"] = c.get("alertas", [])
            it["enfermidades"] = c.get("enfermidades", [])
            it["posologia"] = c.get("posologia", "")
            it["tarja"] = c.get("tarja", it["tarja"])
            it["marcas"] = c.get("marcas", [])
            it["generico"] = c.get("generico", False)
            it["classe"] = it["classe"] or c.get("classe", "")
            it["origem"] = "ANVISA+curado"
            enriquecidos += 1

    # Garante que todo curado exista no catálogo (mesmo sem correspondência na ANVISA)
    for c in curados:
        g = c.get("grupo") or norm(c["principio"])
        if g not in grupos_no_catalogo:
            item = dict(c)
            item["produto"] = c["principio"]
            item["origem"] = "curado"
            itens.append(item)

    # IDs sequenciais e ordena por princípio
    itens.sort(key=lambda x: x["principio"])
    for i, it in enumerate(itens, 1):
        it["id"] = i

    saida = {
        "meta": {
            "projeto": "Farmácia Brasil — Catálogo completo",
            "versao": "3.0",
            "gerado_em": os.environ.get("DATA_BUILD", ""),
            "total": len(itens),
            "enriquecidos_com_curadoria": enriquecidos,
            "fonte": "ANVISA Dados Abertos (medicamentos registrados) + curadoria clínica",
            "aviso": "Ferramenta de apoio. Itens sem curadoria têm tarja 'A confirmar' e dados clínicos na bula da ANVISA. Validar com o farmacêutico responsável.",
        },
        "medicamentos": itens,
    }
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, separators=(",", ":"))
    tam = os.path.getsize(SAIDA) / 1_000_000
    print(f"✅ catalogo.json gerado: {len(itens)} itens, {tam:.1f} MB, {enriquecidos} enriquecidos.")


if __name__ == "__main__":
    main()
