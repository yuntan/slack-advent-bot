from unittest import TestCase, main

from main import (RE_ADVENTAR_URL, RE_QIITA_URL, get_adventar_entries,
                  get_qiita_entries)


class Test(TestCase):
    __re_qiita_url_test_cases = [
        ('http://qiita.com/advent-calendar/2015/python',
         'http://qiita.com/advent-calendar/2015/python'),
        ('<http://qiita.com/advent-calendar/2015/python>',
         'http://qiita.com/advent-calendar/2015/python'),
        ('<http://www.adventar.org/calendars/730>', None),
    ]

    __re_adventar_url_test_cases = [
        ('http://www.adventar.org/calendars/730',
         'http://www.adventar.org/calendars/730'),
        ('<http://www.adventar.org/calendars/730>',
         'http://www.adventar.org/calendars/730'),
        ('<http://qiita.com/advent-calendar/2015/python>', None),
    ]

    # とりあえず1--5日だけテスト
    __get_qiita_entries_test_case = (
        'http://qiita.com/advent-calendar/2015/python', [
            'http://qiita.com/nasa9084/items/40f223b5b44f13ef2925',
            'http://studio3104.hatenablog.com/entry/2015/12/02/120957',
            'http://qiita.com/Tsutomu-KKE@github/items/29414e2d4f30b2bc94ae',
            'http://qiita.com/icoxfog417/items/913bb815d8d419148c33',
            None,
        ])

    __get_adventar_entries_test_case = (
        'http://www.adventar.org/calendars/730', [
            'http://susisu.hatenablog.com/entry/2015/12/01/004809',
            'http://anonemaki.hatenablog.com/entries/2015/12/02',
            'https://gist.github.com/okwrtdsh/9f4f0ab95d0c34349468',
            'http://qiita.com/hayashikun/items/fddcdb7c2f9c687bcc80',
            'http://yuntan-t.hateblo.jp/entry/oucc-advent-2015-12-05',
        ])

    def test_re_qiita_url(self):
        for val, ans in self.__re_qiita_url_test_cases:
            result = RE_QIITA_URL.findall(val)
            if ans:
                self.assertIn(ans, result)
            else:
                self.assertFalse(result)

    def test_re_adventar_url(self):
        for val, ans in self.__re_adventar_url_test_cases:
            result = RE_ADVENTAR_URL.findall(val)
            if ans:
                self.assertIn(ans, result)
            else:
                self.assertFalse(ans)

    def test_get_qiita_entries(self):
        val, ans = Test.__get_qiita_entries_test_case
        result = get_qiita_entries(val)
        self.assertEqual(len(result), 25)
        for r, a in zip(result, ans):
            self.assertEqual(r, a)

    def test_get_adventar_entries(self):
        val, ans = Test.__get_adventar_entries_test_case
        result = get_adventar_entries(val)
        self.assertEqual(len(result), 25)
        for r, a in zip(result, ans):
            self.assertEqual(r, a)

if __name__ == '__main__':
    main()
