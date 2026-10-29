"""Testes offline do leads.py com zips falsos no layout da Receita."""
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import leads  # noqa: E402

HOJE = date(2026, 10, 29)


def estab(basico, fantasia, cnae, uf, mun, ddd, tel, inicio="20180310", situacao="02", matriz="1", sec="", email="contato@x.com.br"):
    c = [""] * 30
    c[0], c[1], c[2], c[3], c[4], c[5] = basico, "0001", "00", matriz, fantasia, situacao
    c[10], c[11], c[12] = inicio, cnae, sec
    c[17], c[19], c[20] = "CENTRO", uf, mun
    c[21], c[22], c[27] = ddd, tel, email
    return c


def escrever_zip(pasta: Path, nome: str, linhas: list[list[str]]):
    texto = "\n".join(";".join(f'"{v}"' for v in l) for l in linhas) + "\n"
    with zipfile.ZipFile(pasta / nome, "w") as z:
        z.writestr(nome.replace(".zip", ".CSV"), texto.encode("latin-1"))


class TestRegras(unittest.TestCase):
    def test_celular(self):
        self.assertEqual(leads.celular("41", "991234567"), "41991234567")
        self.assertEqual(leads.celular("041", "91234567"), "41991234567")  # sem nono dígito
        self.assertIsNone(leads.celular("41", "32221234"))  # fixo
        self.assertIsNone(leads.celular("", "991234567"))

    def test_nome_empresa(self):
        self.assertEqual(leads.nome_empresa("", "JOAO SILVA INSTALACOES ELETRICAS LTDA"), "Joao Silva Instalacoes Eletricas")
        self.assertEqual(leads.nome_empresa("VOLTS SOLAR", "X LTDA"), "Volts Solar")
        self.assertEqual(leads.nome_empresa("", "12.345.678 MARIA DE SOUZA"), "Maria de Souza")

    def test_mensagem_estavel(self):
        modelos = ["A {empresa}", "B {empresa}"]
        r = {"nome": "Felipe", "registro": "CREA-PR"}
        self.assertEqual(leads.montar_mensagem(modelos, r, "X", "Y", "123"), leads.montar_mensagem(modelos, r, "X", "Y", "123"))


class TestWebdav(unittest.TestCase):
    def test_ler_multistatus(self):
        xml = """<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">
          <d:response><d:href>/public.php/dav/files/TOK/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
          <d:response><d:href>/public.php/dav/files/TOK/2026-09/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
          <d:response><d:href>/public.php/dav/files/TOK/2026-09/Estabelecimentos0.zip</d:href><d:propstat><d:prop><d:resourcetype/></d:prop></d:propstat></d:response>
        </d:multistatus>"""
        self.assertEqual(leads.ler_multistatus(xml), [("2026-09", True), ("Estabelecimentos0.zip", False)])


class TestPipeline(unittest.TestCase):
    def test_ponta_a_ponta(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            linhas = [
                estab("11111111", "LUZ FORTE", "4321500", "SC", "8179", "47", "999990001"),
                estab("22222222", "", "4321500", "PR", "7535", "41", "988880002"),       # PR vem primeiro
                estab("33333333", "SO FIXO", "4321500", "PR", "7535", "41", "33330003"),  # sem celular
                estab("44444444", "BAIXADA", "4321500", "PR", "7535", "41", "977770004", situacao="08"),  # baixada
                estab("55555555", "NOVINHA", "4321500", "PR", "7535", "41", "966660005", inicio="20260901"),
                estab("66666666", "PADARIA", "1091102", "PR", "7535", "41", "955550006"),  # outro CNAE
                estab("99999999", "TRACO ARQ", "7111100", "PR", "7535", "41", "911110010"),  # arquitetura
                estab("77777777", "MEI ELETRICA", "4321500", "PR", "7535", "41", "944440007"),
                estab("88888888", "GRANDE SA", "4321500", "PR", "7535", "41", "933330008"),
                estab("22222222", "FILIAL", "4321500", "PR", "7535", "41", "922220009", matriz="2"),
            ]
            escrever_zip(d, "Estabelecimentos0.zip", linhas)
            escrever_zip(d, "Empresas0.zip", [
                ["11111111", "LUZ FORTE ENGENHARIA LTDA", "2062", "49", "10000,00", "03", ""],
                ["22222222", "CARLOS INSTALACOES ELETRICAS LTDA", "2062", "49", "5000,00", "01", ""],
                ["33333333", "SO FIXO LTDA", "2062", "49", "1,00", "01", ""],
                ["55555555", "NOVINHA LTDA", "2062", "49", "1,00", "01", ""],
                ["77777777", "77.777.777 JOSE ELETRICISTA", "2135", "50", "1,00", "01", ""],
                ["88888888", "GRANDE SA", "2054", "10", "9000000,00", "05", ""],
                ["99999999", "TRACO ARQUITETURA LTDA", "2062", "49", "1,00", "01", ""],
            ])
            escrever_zip(d, "Simples.zip", [["77777777", "S", "20200101", "", "S", "20200101", ""]])
            escrever_zip(d, "Municipios.zip", [["7535", "CURITIBA"], ["8179", "JOINVILLE"]])

            cfg = (RAIZ / "prospeccao.toml").read_text(encoding="utf-8").replace("partes = 10", "partes = 1")
            cfg_path = d / "cfg.toml"
            cfg_path.write_text(cfg, encoding="utf-8")
            saida = d / "saida"
            res = leads.executar(saida, cfg_path, d, HOJE)

            self.assertEqual(res["totalAprovadas"], 4)  # inclui a grande (porte 05) e a arquitetura
            self.assertEqual(res["porUf"], {"PR": 3, "SC": 1})
            painel = (saida / "painel.html").read_text(encoding="utf-8")
            ini = painel.index("const LEADS = ") + len("const LEADS = ")
            dados = json.loads(painel[ini:painel.index(";\nconst RESUMO")])
            self.assertEqual([l["empresa"] for l in dados], ["Grande", "Carlos Instalacoes Eletricas", "Traco Arq", "Luz Forte"])
            self.assertEqual(dados[1]["segmento"], "Instalação elétrica")
            self.assertEqual(dados[1]["cidade"], "Curitiba")
            self.assertEqual(dados[1]["celular"], "41988880002")  # matriz, não a filial
            self.assertIn("Carlos Instalacoes Eletricas", dados[1]["mensagem"])
            self.assertIn("instalações elétricas", dados[1]["mensagem"])
            self.assertIn("arquitetura", dados[2]["mensagem"])
            self.assertTrue(all(1 <= l["modelo"] <= 3 for l in dados))
            resumo = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
            self.assertNotIn("41988880002", json.dumps(resumo))  # resumo sem contato


if __name__ == "__main__":
    unittest.main()
