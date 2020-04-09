"""Wrapper for the Python Stanza package.
About: `<https://github.com/stanfordnlp/stanza>`_.
"""

import logging
import os
from typing import Dict, Optional

import stanza  # type: ignore
from stanza.models.common.constant import lang2lcode
from stanza.utils.prepare_resources import default_treebanks

from cltkv1.core.exceptions import UnimplementedLanguageError, UnknownLanguageError
from cltkv1.utils import file_exists, suppress_stdout

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class StanzaWrapper:
    """CLTK's wrapper for the Stanza project."""

    nlps = {}

    def __init__(
        self, language: str, treebank: Optional[str] = None, stanza_debug_level="ERROR"
    ) -> None:
        """Constructor for ``get_stanza_models`` wrapper class.

        TODO: Do tests for all langs and available models for each

        >>> stanza_wrapper = StanzaWrapper(language='grc', stanza_debug_level="INFO")
        >>> isinstance(stanza_wrapper, StanzaWrapper)
        True
        >>> stanza_wrapper.language
        'grc'
        >>> stanza_wrapper.treebank
        'proiel'

        >>> stanza_wrapper = StanzaWrapper(language="grc", treebank="perseus", stanza_debug_level="INFO")
        >>> isinstance(stanza_wrapper, StanzaWrapper)
        True
        >>> stanza_wrapper.language
        'grc'
        >>> stanza_wrapper.treebank
        'perseus'
        >>> from cltkv1.utils.example_texts import get_example_text
        >>> snlp_doc = stanza_wrapper.parse(get_example_text("grc"))

        >>> StanzaWrapper(language="xxx", stanza_debug_level="INFO")
        Traceback (most recent call last):
          ...
        cltkv1.core.exceptions.UnknownLanguageError: Language 'xxx' either not in scope for CLTK or not supported by Stanza.

        >>> stanza_wrapper = StanzaWrapper(language="grc", treebank="proiel", stanza_debug_level="INFO")
        >>> snlp_doc = stanza_wrapper.parse(get_example_text("grc"))

        >>> stanza_wrapper = StanzaWrapper(language="lat", treebank="perseus", stanza_debug_level="INFO")
        >>> snlp_doc = stanza_wrapper.parse(get_example_text("lat"))

        >>> stanza_wrapper = StanzaWrapper(language="lat", treebank="proiel", stanza_debug_level="INFO")
        >>> snlp_doc = stanza_wrapper.parse(get_example_text("lat"))

        >>> stanza_wrapper = StanzaWrapper(language="chu", stanza_debug_level="INFO")
        >>> snlp_doc = stanza_wrapper.parse(get_example_text("chu"))

        >>> stanza_wrapper = StanzaWrapper(language="lat", treebank="xxx", stanza_debug_level="INFO")
        Traceback (most recent call last):
          ...
        cltkv1.core.exceptions.UnimplementedLanguageError: Invalid treebank 'xxx' for language 'lat'.
        """
        self.language = language
        self.treebank = treebank
        self.stanza_debug_level = stanza_debug_level

        # Setup language
        self.map_langs_cltk_stanza = {
            "grc": "Ancient_Greek",
            "lat": "Latin",
            "chu": "Old_Church_Slavonic",
            "fro": "Old_French",
            "got": "Gothic",
        }

        self.wrapper_available = self.is_wrapper_available()  # type: bool
        if not self.wrapper_available:
            raise UnknownLanguageError(
                "Language '{}' either not in scope for CLTK or not supported by Stanza.".format(
                    self.language
                )
            )
        self.stanza_code = self._get_stanza_code()

        # Setup optional treebank if specified
        # TODO: Write tests for all treebanks
        self.map_code_treebanks = dict(
            grc=["proiel", "perseus"], la=["perseus", "proiel", "ittb"]
        )
        # if not specified, will use the default treebank chosen by stanza
        if self.treebank:
            valid_treebank = self._is_valid_treebank()
            if not valid_treebank:
                raise UnimplementedLanguageError(
                    f"Invalid treebank '{self.treebank}' for language '{self.language}'."
                )
        else:
            self.treebank = self._get_default_treebank()

        # check if model present
        # this fp is just to confirm that some model has already been downloaded.
        # TODO: This is a weak check for the models actually being downloaded and valid
        # TODO: Use ``models_dir`` var from below and make self. or global to module
        self.model_path = os.path.expanduser(
            f"~/stanza_resources/{self.stanza_code}/tokenize/{self.treebank}.pt"
        )
        if not self._is_model_present():
            # download model if necessary
            self._download_model()

        # instantiate actual stanza class
        # Note: `suppress_stdout` is used to prevent `stanza`
        # from printing a long log of its parameters to screen.
        # Though we should capture these, within `_load_pipeline()`,
        # for the log file.
        with suppress_stdout():
            self.nlp = self._load_pipeline()

    def parse(self, text: str):
        """Run all available ``stanza`` parsing on input text.

        >>> from cltkv1.utils.example_texts import get_example_text
        >>> stanza_wrapper = StanzaWrapper(language='grc', stanza_debug_level="INFO")
        >>> greek_nlp = stanza_wrapper.parse(get_example_text("grc"))
        >>> from stanza.models.common.doc import Document, Token
        >>> isinstance(greek_nlp, Document)
        True

        >>> nlp_greek_first_sent = greek_nlp.sentences[0]
        >>> isinstance(nlp_greek_first_sent.tokens[0], Token)
        True
        >>> nlp_greek_first_sent.tokens[0].text
        'ὅτι'
        >>> nlp_greek_first_sent.tokens[0].words
        [{
          "id": "1",
          "text": "ὅτι",
          "lemma": "ὅτι",
          "upos": "ADV",
          "xpos": "Df",
          "head": 7,
          "deprel": "advmod",
          "misc": "start_char=0|end_char=3"
        }]
        >>> nlp_greek_first_sent.tokens[0].start_char
        0
        >>> nlp_greek_first_sent.tokens[0].end_char
        3
        >>> nlp_greek_first_sent.tokens[0].misc
        'start_char=0|end_char=3'
        >>> nlp_greek_first_sent.tokens[0].pretty_print()
        '<Token id=1;words=[<Word id=1;text=ὅτι;lemma=ὅτι;upos=ADV;xpos=Df;head=7;deprel=advmod>]>'
        >>> nlp_greek_first_sent.tokens[0].to_dict()
        [{'id': '1', 'text': 'ὅτι', 'lemma': 'ὅτι', 'upos': 'ADV', 'xpos': 'Df', 'head': 7, 'deprel': 'advmod', 'misc': 'start_char=0|end_char=3'}]

        >>> first_word = nlp_greek_first_sent.tokens[0].words[0]
        >>> first_word.id
        '1'
        >>> first_word.text
        'ὅτι'
        >>> first_word.lemma
        'ὅτι'
        >>> first_word.upos
        'ADV'
        >>> first_word.xpos
        'Df'
        >>> first_word.feats
        >>> first_word.head
        7
        >>> first_word.parent
        [
          {
            "id": "1",
            "text": "ὅτι",
            "lemma": "ὅτι",
            "upos": "ADV",
            "xpos": "Df",
            "head": 7,
            "deprel": "advmod",
            "misc": "start_char=0|end_char=3"
          }
        ]
        >>> first_word.misc
        'start_char=0|end_char=3'
        >>> first_word.deprel
        'advmod'
        >>> first_word.pos
        'ADV'
        """
        parsed_text = self.nlp(text)
        return parsed_text

    def _load_pipeline(self):
        """Instantiate ``stanza.Pipeline()``.

        TODO: Make sure that logging captures what it should from the default stanza printout.
        TODO: Make note that full lemmatization is not possible for Old French

        >>> stanza_wrapper = StanzaWrapper(language='grc', stanza_debug_level="INFO")
        >>> with suppress_stdout():    nlp_obj = stanza_wrapper._load_pipeline()
        >>> isinstance(nlp_obj, stanza.pipeline.core.Pipeline)
        True
        >>> stanza_wrapper = StanzaWrapper(language='fro', stanza_debug_level="INFO")
        >>> with suppress_stdout():    nlp_obj = stanza_wrapper._load_pipeline()
        >>> isinstance(nlp_obj, stanza.pipeline.core.Pipeline)
        True
        """
        models_dir = os.path.expanduser(
            "~/stanza_resources/"
        )  # TODO: Mv this a self. var or maybe even global
        lemma_use_identity = False
        if self.language == "fro":
            processors = "tokenize,pos,lemma"
            lemma_use_identity = True
        else:
            processors = "tokenize,mwt,pos,lemma,depparse"

        # def __init__(self, lang='en', dir=DEFAULT_MODEL_DIR, package='default', processors={}, logging_level='INFO', verbose=None, use_gpu=True, **kwargs)
        nlp = stanza.Pipeline(
            lang=self.stanza_code,
            dir=models_dir,
            package=self.treebank,
            processors=processors,  # these are the default processors
            logging_level=self.stanza_debug_level,
            use_gpu=True,  # default, won't fail if GPU not present
            lemma_use_identity=lemma_use_identity,
        )
        return nlp

    def _is_model_present(self) -> bool:
        """Checks if the model is already downloaded.

        >>> stanza_wrapper = StanzaWrapper(language='grc', stanza_debug_level="INFO")
        >>> stanza_wrapper._is_model_present()
        True
        """
        if file_exists(self.model_path):
            return True
        return False

    def _download_model(self) -> None:
        """Interface with the `stanza` model downloader.

        TODO: (old) Figure out why doctests here hang. Presumably because waiting for user op_input, but prompt shouldn't arise if models already present.

        # >>> stanza_wrapper = StanzaWrapper(language='grc', stanza_debug_level="INFO")
        # >>> stanza_wrapper._download_model()
        # True
        """
        # TODO: Add prompt whether to allow stanza to download files
        # prompt user to DL the get_stanza_models models
        print("")  # pragma: no cover
        print("")  # pragma: no cover
        print("Α" * 80)  # pragma: no cover
        print("")  # pragma: no cover
        print(  # pragma: no cover
            "CLTK message: The part of the CLTK that you are using depends upon the Stanza NLP library (`stanza`). What follows are several question prompts coming from it. (More at: <https://github.com/stanza/stanza>.) Answer with defaults."
        )  # pragma: no cover
        print("")  # pragma: no cover
        print("Ω" * 80)  # pragma: no cover
        print("")  # pragma: no cover
        print("")  # pragma: no cover
        stanza.download(lang=self.language, package=self.treebank)
        # if file model still not available after attempted DL, then raise error
        if not file_exists(self.model_path):
            raise FileNotFoundError(
                "Missing required models for ``stanza`` at ``{0}``.".format(
                    self.model_path
                )
            )

    def _get_default_treebank(self) -> str:
        """Return description of a language's default treebank if none
        supplied.

        >>> stanza_wrapper = StanzaWrapper(language='grc', stanza_debug_level="INFO")
        >>> stanza_wrapper._get_default_treebank()
        'proiel'
        """
        stanza_default_treebanks = default_treebanks  # type: Dict[str, str]
        return stanza_default_treebanks[self.stanza_code]

    def _is_valid_treebank(self) -> bool:
        """Check whether for chosen language, optional
        treebank value is valid.

        >>> stanza_wrapper = StanzaWrapper(language='grc', treebank='proiel', stanza_debug_level="INFO")
        >>> stanza_wrapper._is_valid_treebank()
        True
        """
        possible_treebanks = self.map_code_treebanks[self.stanza_code]
        if self.treebank in possible_treebanks:
            return True
        return False

    def is_wrapper_available(self) -> bool:
        """Maps an ISO 639-3 language id (e.g., ``lat`` for Latin) to
        that used by ``stanza`` (``la``); confirms that this is
        a language the CLTK supports (i.e., is it pre-modern or not).

        >>> stanza_wrapper = StanzaWrapper(language='grc', stanza_debug_level="INFO")
        >>> stanza_wrapper.is_wrapper_available()
        True
        """
        if self.language in self.map_langs_cltk_stanza:
            return True
        return False

    def _get_stanza_code(self) -> str:
        """Using known-supported language, use the CLTK's
        internal code to look up the code used by Stanza.

        >>> stanza_wrapper = StanzaWrapper(language='grc', stanza_debug_level="INFO")
        >>> stanza_wrapper._get_stanza_code()
        'grc'
        >>> stanza_wrapper.language = "xxx"
        >>> stanza_wrapper._get_stanza_code()
        Traceback (most recent call last):
          ...
        KeyError: 'Somehow ``StanzaWrapper.language`` got renamed to something invalid. This should never happen.'
        """
        try:
            stanza_lang_name = self.map_langs_cltk_stanza[self.language]
        except KeyError:
            raise KeyError(
                "Somehow ``StanzaWrapper.language`` got renamed to something invalid. This should never happen."
            )
        # {'Afrikaans': 'af', 'Ancient_Greek': 'grc', ...}
        stanza_lang_code = lang2lcode  # type: Dict[str, str]
        try:
            return stanza_lang_code[stanza_lang_name]
        except KeyError:
            raise KeyError("The CLTK's map of ISO-to-Stanza is out of sync.")

    @classmethod
    def get_nlp(cls, language: str, treebank: Optional[str] = None):
        if language in cls.nlps:
            return cls.nlps[language]
        else:
            nlp = cls(language, treebank)
            cls.nlps[language] = nlp
            return nlp
