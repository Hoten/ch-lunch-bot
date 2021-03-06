import urllib.request, re, os, json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from slackclient import SlackClient

DISCOUNT_RATE = 0.6

class MenuSection:
  def __init__(self, name, entree, ingredients, macros, prices):
    self.name = name
    self.entree = entree
    self.ingredients = ingredients
    self.macros = macros
    self.prices = prices

  def __repr__(self):
    return str(self.__dict__)


def is_float(value):
    try:
      float(value)
      return True
    except ValueError:
      return False

def apply_discount(p):
  return round(p * DISCOUNT_RATE, 2) if is_float(p) else f'{p} (minus discount)'

def get_soup(today):
  dayofweek = today.weekday()
  last_monday = today - timedelta(days=dayofweek)
  week_part = last_monday.strftime('%m-%d-%Y')
  url = f'http://dining.guckenheimer.com/clients/informatica/fss/fss.nsf/weeklyMenuLaunch/AJSQ22~{week_part}/$file/day{dayofweek + 1}.htm'
  raw_html = urllib.request.urlopen(url).read()
  return BeautifulSoup(raw_html, 'html.parser')

def parse_sections(all_elems):
  def parse_prices(text):
    return [(float(x) if is_float(x) else x) for x in text.split('/')]

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
      macros = None
      prices = parse_prices(elems_for_section[2].get_text())

    if length == 4:
      name = elems_for_section[0].get_text().strip()
      entree = elems_for_section[1].get_text().strip()
      ingredients = elems_for_section[2].replace('Ingredients: ', '').strip()
      macros = None
      prices = parse_prices(elems_for_section[3].get_text())

    if length == 5:
      name = elems_for_section[0].get_text().strip()
      entree = elems_for_section[1].get_text().strip()
      ingredients = elems_for_section[2].replace('Ingredients: ', '').strip()
      macros = elems_for_section[3].get_text().strip()
      prices = parse_prices(elems_for_section[4].get_text())

    sections.append(MenuSection(
      name,
      entree,
      ingredients,
      macros,
      prices
    ))

  return sections

def render_message(sections):
  def format_prices(prices):
    return '/'.join([('${:,.2f}'.format(p) if is_float(p) else p) for p in prices])

  lines = []
  for section in sections:
    lines.append(f'*{section.name}*')
    lines.append(f'{section.entree}')
    
    if section.ingredients:
      lines.append(f'{section.ingredients}')

    if section.macros:
      lines.append(f'{section.macros}')

    discounted_prices = [apply_discount(p) for p in section.prices]
    lines.append(f'~{format_prices(section.prices)}~ {format_prices(discounted_prices)}')
    lines.append('')

  return '\n'.join(lines)

def ensure(condition):
  if not condition:
    raise Exception('data not good')

def post(message, channel):
  slack_token = os.environ['SLACK_API_TOKEN']
  sc = SlackClient(slack_token)

  sc.api_call(
    'chat.postMessage',
    channel=channel,
    username='LunchBot',
    icon_emoji=':eating:',
    text=message,
    unfurl_media=True,
    unfurl_links=True
  )

def get_burrito():
  giphy_token = os.environ['GIPHY_API_TOKEN']
  raw_data = urllib.request.urlopen(f"https://api.giphy.com/v1/gifs/random?api_key={giphy_token}&tag=burrito&rating=PG").read()
  data = json.loads(raw_data.decode('utf-8'))['data']
  images = data['images']
  
  if 'fixed_width' in images:
    return images['fixed_width']['url']

  if 'downsized' in images:
    return images['downsized']['url']

  return images['embed_url']

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
    post(message, '#lunch')
    if re.search('burrito', message, re.IGNORECASE):
      post("It's Burrito Day!\n" + get_burrito(), '@kevinwilde')

def call(event, context):
  dry_run = 'dry_run' in event and event['dry_run']
  run(dry_run)
  return 'Done'
