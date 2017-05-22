import re
from os.path import join

from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize

from django.conf import settings


def replace_all(text, dic):
    for i, j in list(dic.items()):
        text = text.replace(i, j)
    return text


def scoreFunction(wholetext):
    """Get text, find most common words and compare with known
    stopwords. Return dictionary of values"""

    dictiolist = {}
    scorelist = {}
    # These are the available languages with stopwords from NLTK
    NLTKlanguages=["dutch","finnish","german","italian", "portuguese",
        "spanish","turkish","danish","english", "french","hungarian",
        "norwegian","russian","swedish"]

    FREElanguages = [""]
    languages=NLTKlanguages + FREElanguages

    # Fill the dictionary of languages, to avoid  unnecessary function calls
    for lang in NLTKlanguages:
        dictiolist[lang] = stopwords.words(lang)

    # Split all the text in tokens and convert to lowercase. In a
    # decent version of this, I'd also clean the unicode
    tokens = nltk.tokenize.word_tokenize(wholetext)
    tokens = [t.lower() for t in tokens]

    # Determine the frequency distribution of words, looking for the
    # most common words
    freq_dist = nltk.FreqDist(tokens)

    # This is the only interesting piece, and not by much. Pick a
    # language, and check if each of the 20 most common words is in
    # the language stopwords. If it's there, add 1 to this language
    # for each word matched. So the maximal score is 20. Why 20? No
    # specific reason, looks like a good number of words.
    for lang in languages:
        scorelist[lang]=0
        for word in freq_dist.keys()[0:20]:
            if word in dictiolist[lang]:
                scorelist[lang]+=1
    return scorelist

def whichLanguage(scorelist):
    """This function just returns the language name, from a given
    "scorelist" dictionary as defined in scoreFunction()."""

    maximum = 0
    for item in scorelist:
        value=scorelist[item]
        if maximum<value:
            maximum = value
            lang = item
    return lang


class Autolinker(object):
    ignoreCaseLength = 12

    def __init__(self):
        self.links = {}
        #any item that gets added must have a linkHTML method that accepts a title parameter

    def addItem(self, title, item):
        self.links[title] = item

    def addLinks(self, links):
        for link in links:
            self.links[link.title()] = link

    def replaceAll(self, haystack):
        for title, link in sorted(list(self.links.items()), key=lambda x:-len(x[0])):
            haystack = self.replace(title, link, haystack)
            #we're going paragraph-by-paragraph, but don't want multiple links
            if self.replaced:
                del self.links[title]
        return haystack

    def regexOptions(self, text):
        options = re.DOTALL
        if len(text) > self.ignoreCaseLength:
            options = options | re.IGNORECASE
        return options

    def replace(self, needle, replacement, haystack):
        self.replacement = replacement
        options = self.regexOptions(needle)
        needle = re.compile('([^{}]*?)(' + re.escape(needle) + ')([^{}]*)', options)
        self.needle = needle
        self.replaced = False
        return self.doReplace(haystack)

    def doReplace(self, haystack):
        return re.sub(self.needle, self.matcher, haystack)

    def matcher(self, match):
        fullText = match.group(0)
        if not self.replaced:
            #if it's inside of a django tag, don't make the change
            if fullText[0] == '%' or fullText[-1] == '%':
                return fullText
                #if it's inside of a link already, don't make the change
                leftText = match.group(1)
                matchText = match.group(2)
                rightText = match.group(3)
                rightmostAnchor = leftText.rfind('<a')
                if rightmostAnchor != -1:
                    anchorClose = leftText.rfind('</a>')
                    if anchorClose < rightmostAnchor:
                        #this is inside of an open a tag.
                        #but there might be a match in the rightText
                        fullText = leftText+matchText + self.doReplace(rightText)
                        return fullText
                        #check the right side for anchors, too.
                        leftmostAnchorClose = rightText.find('</a>')
                        if leftmostAnchorClose != -1:
                            anchorOpen = rightText.find('<a')
                            if anchorOpen == -1 or anchorOpen > leftmostAnchorClose:
                                #this is inside of an open a tag
                                return fullText
                                #otherwise, it is safe to make the change
                                fullText = leftText + self.replacement.linkHTML(title=matchText) + rightText
                                self.replaced = True
                                return fullText


async def text_cleaner(data):
    keep_endings = ['.', '?']

    removals_ = open(join(settings.BASE_DIR, "aggregator", 'data', 'stop_sentences.txt'), 'r')
    removals = [r.replace('\n', '') for r in removals_]

    text = data.split('\n')
    paragraphs = []
    for p in text:
        if len(p) > settings.MINIMUM_PARAGRAPH:
            paragraphs.append(p)

    paragraphs_ = ""
    for p in paragraphs:
        sentence_tokens = sent_tokenize(p)
        paragraph = ""
        for sentence in sentence_tokens:
            if sentence[-1] in keep_endings:
                    if len(sentence) > settings.MINIMUM_SENTENCE:
                        #should remove most of the code:
                        if sentence[0].isupper():
                            if not any(to_remove in sentence for to_remove in removals):
                                #eliminate some bad ending strings:
                                if not sentence.endswith(('e.g.', 'i.e.')):
                                    paragraph += "{0} ".format(sentence)
        paragraphs_ +=  "<p>{0}</p>".format(paragraph)

    return paragraphs_
