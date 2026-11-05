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


class TestContratos(unittest.TestCase):
    LIC = None

    @classmethod
    def setUpClass(cls):
        import tomllib
        cls.LIC = tomllib.loads((RAIZ / "prospeccao.toml").read_text(encoding="utf-8"))["licitacoes"]

    def contrato(self, objeto, ni="12345678000190", valor=250000.0):
        return {"niFornecedor": ni, "tipoPessoa": "PJ", "objetoContrato": objeto, "valorGlobal": valor,
                "dataAssinatura": "2026-10-20T00:00:00", "anoContrato": 2026, "sequencialContrato": 7,
                "orgaoEntidade": {"cnpj": "76417005000186", "razaoSocial": "MUNICIPIO DE PONTA GROSSA"},
                "unidadeOrgao": {"ufSigla": "PR"}}

    def test_aceita_obra_eletrica(self):
        s = leads.classificar_contrato(self.contrato("EXECUÇÃO DE OBRA DE REFORMA DA REDE ELÉTRICA DA ESCOLA X"), self.LIC)
        self.assertEqual(s["cnpj"], "12345678000190")
        self.assertEqual(s["orgao"], "Municipio de Ponta Grossa")
        self.assertTrue(s["objeto"].startswith("execução de obra"))
        self.assertIn("/app/contratos/76417005000186/2026/7", s["link"])

    def test_descarta(self):
        c = leads.classificar_contrato
        self.assertIsNone(c(self.contrato("FORNECIMENTO DE ENERGIA ELÉTRICA PARA A SEDE"), self.LIC))
        self.assertIsNone(c(self.contrato("AQUISIÇÃO DE MATERIAL ELÉTRICO"), self.LIC))  # sem serviço
        self.assertIsNone(c(self.contrato("MANUTENÇÃO DE VEÍCULOS"), self.LIC))
        self.assertIsNone(c(self.contrato("INSTALAÇÃO ELÉTRICA", ni="12345678900"), self.LIC))  # pessoa física
        self.assertIsNone(c(self.contrato("INSTALAÇÃO ELÉTRICA", valor=5000), self.LIC))


class TestPipeline(unittest.TestCase):
    def test_ponta_a_ponta(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            velho = "20100310"
            linhas = [
                estab("11111111", "LUZ FORTE", "4321500", "SC", "8179", "47", "999990001", inicio=velho),
                estab("22222222", "", "4321500", "PR", "7535", "41", "988880002", inicio=velho),  # PR vem primeiro
                estab("33333333", "SO FIXO", "4321500", "PR", "7535", "41", "33330003", inicio=velho),  # sem celular
                estab("44444444", "BAIXADA", "4321500", "PR", "7535", "41", "977770004", inicio=velho, situacao="08"),
                estab("55555555", "NOVINHA", "4321500", "PR", "7535", "41", "966660005", inicio="20200901"),  # < 10 anos
                estab("66666666", "PADARIA", "1091102", "PR", "7535", "41", "955550006", inicio=velho),  # outro CNAE
                estab("99999999", "TRACO ARQ", "7111100", "PR", "7535", "41", "911110010", inicio=velho),
                estab("77777777", "MEI ELETRICA", "4321500", "PR", "7535", "41", "944440007", inicio=velho),
                estab("88888888", "FORA DO SIMPLES", "4321500", "PR", "7535", "41", "933330008", inicio=velho),
                estab("12121212", "SILVA ADVOGADOS", "6911701", "PR", "7535", "41", "912120012", inicio=velho),
                estab("13131313", "CONSTRUTORA VENCE", "4120400", "PR", "7535", "41", "913130013", inicio="20230101"),
                estab("14141414", "EM RECUPERACAO", "4321500", "PR", "7535", "41", "914140014", inicio=velho),
                estab("15151515", "GAUCHA", "4321500", "RS", "8801", "51", "915150015", inicio=velho),  # fora de PR/SC/SP
                estab("22222222", "FILIAL", "4321500", "PR", "7535", "41", "922220009", matriz="2", inicio=velho),
            ]
            escrever_zip(d, "Estabelecimentos0.zip", linhas)
            escrever_zip(d, "Empresas0.zip", [
                ["11111111", "LUZ FORTE ENGENHARIA LTDA", "2062", "49", "10000,00", "03", ""],
                ["22222222", "CARLOS INSTALACOES ELETRICAS LTDA", "2062", "49", "5000,00", "01", ""],
                ["33333333", "SO FIXO LTDA", "2062", "49", "1,00", "01", ""],
                ["55555555", "NOVINHA LTDA", "2062", "49", "1,00", "01", ""],
                ["77777777", "77.777.777 JOSE ELETRICISTA", "2135", "50", "1,00", "01", ""],
                ["88888888", "FORA DO SIMPLES LTDA", "2062", "49", "1,00", "03", ""],
                ["99999999", "TRACO ARQUITETURA LTDA", "2062", "49", "1,00", "01", ""],
                ["12121212", "SILVA E SOUZA SOCIEDADE DE ADVOGADOS", "2232", "49", "1,00", "01", ""],
                ["13131313", "CONSTRUTORA VENCE LTDA", "2062", "49", "1,00", "05", ""],
                ["14141414", "ELETRICA X LTDA EM RECUPERACAO JUDICIAL", "2062", "49", "1,00", "01", ""],
                ["15151515", "GAUCHA ELETRICA LTDA", "2062", "49", "1,00", "01", ""],
            ])
            simples = [[b, "S", "20120101", "", "N", "", ""] for b in
                       ["11111111", "22222222", "33333333", "55555555", "99999999", "12121212", "14141414", "15151515"]]
            simples.append(["77777777", "S", "20200101", "", "S", "20200101", ""])
            escrever_zip(d, "Simples.zip", simples)
            escrever_zip(d, "Municipios.zip", [["7535", "CURITIBA"], ["8179", "JOINVILLE"]])
            contratos = d / "contratos.json"
            contratos.write_text(json.dumps({"data": [{
                "niFornecedor": "13131313000100", "tipoPessoa": "PJ", "valorGlobal": 480000,
                "objetoContrato": "EXECUÇÃO DE SERVIÇOS DE MANUTENÇÃO DA ILUMINAÇÃO PÚBLICA",
                "dataAssinatura": "2026-10-21", "anoContrato": 2026, "sequencialContrato": 3,
                "orgaoEntidade": {"cnpj": "76417005000186", "razaoSocial": "MUNICIPIO DE PONTA GROSSA"},
                "unidadeOrgao": {"ufSigla": "PR"}}]}), encoding="utf-8")

            cfg = (RAIZ / "prospeccao.toml").read_text(encoding="utf-8").replace("partes = 10", "partes = 1")
            cfg_path = d / "cfg.toml"
            cfg_path.write_text(cfg, encoding="utf-8")
            saida = d / "saida"
            res = leads.executar(saida, cfg_path, d, HOJE, contratos=contratos)

            self.assertEqual(res["totalAprovadas"], 5)
            self.assertEqual(res["porTrilha"], {"licitacao": 1, "pericia": 1, "projeto": 3})
            self.assertEqual(res["etapas"]["fora_do_simples"], 1)
            self.assertEqual(res["etapas"]["nome_excluido"], 1)
            painel = (saida / "painel.html").read_text(encoding="utf-8")
            ini = painel.index("const LEADS = ") + len("const LEADS = ")
            dados = json.loads(painel[ini:painel.index(";\nconst RESUMO")])
            por_nome = {l["empresa"]: l for l in dados}
            self.assertEqual(set(por_nome), {"Construtora Vence", "Silva Advogados", "Carlos Instalacoes Eletricas",
                                             "Traco Arq", "Luz Forte"})
            vence = por_nome["Construtora Vence"]
            self.assertEqual((vence["trilha"], vence["segmento"]), ("licitacao", "Venceu licitação"))
            self.assertIn("Municipio de Ponta Grossa", vence["mensagem"])
            self.assertIn("iluminação pública", vence["mensagem"])
            self.assertEqual(vence["sinal"]["assinatura"], "21/10/2026")
            adv = por_nome["Silva Advogados"]
            self.assertEqual(adv["trilha"], "pericia")
            self.assertIn("assistente técnico", adv["mensagem"])
            self.assertNotIn("periculosidade", adv["mensagem"])
            carlos = por_nome["Carlos Instalacoes Eletricas"]
            self.assertEqual(carlos["celular"], "41988880002")  # matriz, não a filial
            self.assertIn("instalações elétricas", carlos["mensagem"])
            self.assertIn("const FILA = {", painel)
            self.assertTrue(all(1 <= l["modelo"] <= 3 for l in dados))
            resumo = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
            self.assertNotIn("41988880002", json.dumps(resumo))  # resumo sem contato


if __name__ == "__main__":
    unittest.main()
