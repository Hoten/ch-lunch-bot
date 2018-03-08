import urllib.request, re, os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from slackclient import SlackClient

DISCOUNT_RATE = 0.6

class MenuSection:
  def __init__(self, name, entree, ingredients, prices):
    self.name = name
    self.entree = entree
    self.ingredients = ingredients
    self.prices = prices

  def __repr__(self):
    return str(self.__dict__)

def get_soup(today):
  dayofweek = today.weekday()
  last_monday = today - timedelta(days=dayofweek)
  week_part = last_monday.strftime('%m-%d-%Y')
  url = f'http://dining.guckenheimer.com/clients/informatica/fss/fss.nsf/weeklyMenuLaunch/AJSQ22~{week_part}/$file/day{dayofweek + 1}.htm'
  raw_html = urllib.request.urlopen(url).read()
  return BeautifulSoup(raw_html, 'html.parser')

def parse_sections(all_elems):
  def parse_prices(text):
    return [float(x) for x in text.split('/')]

  grouped_elems = []

  grouped_elems.append([])
  for elem in all_elems:
    if elem.name == 'br':
      grouped_elems.append([])
    else:
      grouped_elems[-1].append(elem)

  sections = []
  for elems_for_section in grouped_elems:
    length = len(elems_for_section)

    if length == 0:
      continue

    if length == 3:
      name = elems_for_section[0].get_text().strip()
      entree = elems_for_section[1].get_text().strip()
      ingredients = None
      prices = parse_prices(elems_for_section[2].get_text())

    if length == 4:
      name = elems_for_section[0].get_text().strip()
      entree = elems_for_section[1].get_text().strip()
      ingredients = elems_for_section[2].replace('Ingredients: ', '').strip()
      prices = parse_prices(elems_for_section[3].get_text())

    sections.append(MenuSection(
      name,
      entree,
      ingredients,
      prices
    ))

  return sections

def render_message(sections):
  def format_prices(prices):
    return '/'.join(['${:,.2f}'.format(p) for p in prices])

  lines = []
  for section in sections:
    lines.append(f'*{section.name}*')
    lines.append(f'{section.entree}')
    
    if section.ingredients:
      lines.append(f'{section.ingredients}')

    discounted_prices = [round(p * DISCOUNT_RATE, 2) for p in section.prices]
    lines.append(f'~{format_prices(section.prices)}~ {format_prices(discounted_prices)}')
    lines.append('')

  return '\n'.join(lines)

def ensure(condition):
  if not condition:
    raise Exception('data not good')

def post(message):
  slack_token = os.environ['SLACK_API_TOKEN']
  sc = SlackClient(slack_token)

  sc.api_call(
    'chat.postMessage',
    channel='#lunch',
    username='LunchBot',
    text=message
  )

def run(dry_run):
  today = datetime.today()
  if today.weekday() >= 5:
    return

  soup = get_soup(today)
  sections = parse_sections(soup.find(id='center_text'))
  ensure(len(sections) > 0)
  message = render_message(sections)
  
  print(message)
  if (not dry_run):
    post(message)

def call(event, context):
  dry_run = hasattr(event, 'dry_run') and event.dry_run
  run(dry_run)
  return 'Done'
