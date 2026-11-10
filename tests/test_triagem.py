import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prospeccao"))
import triagem as t  # noqa: E402

LEADS = [
    {"cnpj": "11111111000111", "empresa": "Alfa Elétrica", "celular": "41999998888", "cidade": "Curitiba", "uf": "PR"},
    {"cnpj": "22222222000122", "empresa": "Beta Obras", "celular": "4733334444", "cidade": "Joinville", "uf": "SC"},
    {"cnpj": "33333333000133", "empresa": "Gama", "celular": "41988887777", "cidade": "Curitiba", "uf": "PR"},
]
PAINEL = "<script>\n/* LEADS_DATA_START */\nconst LEADS = " + json.dumps(LEADS) + ";\nconst RESUMO = null;\nconst FILA = {};\n/* LEADS_DATA_END */\n</script>"


class TestTriagem(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "painel.html").write_text(PAINEL, encoding="utf-8")
        self.leads = t.ler_leads(self.tmp / "painel.html")

    def test_fone(self):
        self.assertEqual(t.fone_wa("41999998888"), "+55 41 99999-8888")
        self.assertEqual(t.fone_wa("4733334444"), "+55 47 3333-4444")

    def test_dias_uteis(self):
        self.assertEqual(t.dias_uteis(date(2026, 11, 3), date(2026, 11, 10)), 5)

    def test_lista_e_padrao(self):
        status = {
            "11111111000111": {"status": "contatado", "contatadoEm": "2026-10-13T12:00:00Z", "followupEm": "2026-10-20T12:00:00Z"},
            "22222222000122": {"status": "respondeu", "contatadoEm": "2026-11-05T12:00:00Z"},
            "33333333000133": {"status": "contatado", "contatadoEm": "2026-11-05T12:00:00Z"},
        }
        triagem = {"33333333000133-1": {"cnpj": "33333333000133", "status": "futuro", "em": "2026-11-09T20:00:00Z"}}
        itens, cont = t.montar_lista(self.leads, status, triagem, date(2026, 11, 10))
        self.assertEqual([i["cnpj"] for i in itens], ["22222222000122", "11111111000111"])  # respondeu primeiro
        self.assertEqual(cont["com_sugestao_pendente"], 1)
        status["44444444000144"] = {"status": "contatado", "contatadoEm": "2026-11-05T12:00:00Z", "empresa": "Delta", "celular": "41977776666"}
        status["55555555000155"] = {"status": "contatado", "contatadoEm": "2026-11-05T12:00:00Z", "empresa": "Épsilon"}
        itens2, cont2 = t.montar_lista(self.leads, status, triagem, date(2026, 11, 10))
        fones = {i["cnpj"]: i["fone"] for i in itens2}
        self.assertEqual(fones["44444444000144"], "+55 41 97777-6666")
        self.assertEqual(fones["55555555000155"], "BUSCAR PELO NOME")
        self.assertEqual(cont2["sem_telefone"], 1)
        del status["44444444000144"], status["55555555000155"]
        self.assertEqual(itens[1]["padrao"]["status"], "sem_resposta")
        self.assertIsNone(itens[0]["padrao"])
        status["11111111000111"]["retomadoEm"] = "2026-11-06T12:00:00Z"   # retomada recente: ainda aguarda
        itens, _ = t.montar_lista(self.leads, status, {}, date(2026, 11, 10))
        self.assertIsNone([i for i in itens if i["cnpj"] == "11111111000111"][0]["padrao"])

    def test_gravar(self):
        achados = [
            {"cnpj": "11.111.111/0001-11", "status": "respondeu", "motivo": "Pediu orçamento de SPDA",
             "rascunho": "Oi! Me passa a área e a cidade? Meu cel é 41 99999-8888", "ultimaMsgEm": "2026-11-10T14:00"},
            {"cnpj": "22222222000122", "status": "futuro", "motivo": "Disse que em 2027 terá obra"},
            {"cnpj": "99999999000199", "status": "respondeu", "motivo": "x"},
            {"cnpj": "33333333000133", "status": "a_contatar", "motivo": "x"},
        ]
        agora = datetime(2026, 11, 10, 20, 41, tzinfo=timezone.utc)
        lotes, erros, cont = t.montar_gravacao(achados, self.leads, agora, self.tmp / "saida",
                                               {"11111111000111": {"status": "contatado"}})
        self.assertEqual(len(erros), 2)
        self.assertEqual(cont, {"respondeu": 1, "futuro": 1})
        w = lotes[0][0]
        self.assertEqual(w["collection"], "triagem")
        self.assertEqual(w["doc_id"], "11111111000111-202611101741")
        doc = json.loads(Path(w["file_path"]).read_text(encoding="utf-8"))
        self.assertIn("[telefone]", doc["rascunho"])
        self.assertNotIn("99999-8888", doc["rascunho"])
        self.assertTrue(doc["auto"])
        self.assertEqual(doc["de"], "contatado")
        doc2 = json.loads(Path(lotes[0][1]["file_path"]).read_text(encoding="utf-8"))
        self.assertEqual(doc2["retomarEm"], "2026-12-10")
        self.assertIn("responderam", t.resumo_notificacao(cont))


if __name__ == "__main__":
    unittest.main()
