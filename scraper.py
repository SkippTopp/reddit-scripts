import datetime
import argparse

import grab
from grab.spider import Spider,Task
from grab import Grab
from openpyxl import Workbook

# Headers for excel file.
post_headers = ["Post Title", "Post Date/Time", "Posted By", "# Comments", 
				"Karma Points", "Upvote %"]
comment_headers = ["Post Title", "Original Poster", "Commenter", "Comment Date/Time",
					"# Replies", "Karma Points"]

def parse_args():
	parser = argparse.ArgumentParser(
		description=""" This script scrapes a subreddit of you choice.
						It returns two excel files: 
		
						(1) File with all subreddit posts. 
						The data it will contain for each post:
						Post Title | Post Date/Time | Posted By |# Comments |Karma Points | Upvote %
		
						(2) File with all comments to all posts in a subreddit. 
						The data it will contain for each comment:
						Post Title | Original Poster | Commenter | Comment Date/Time | # Replies | Karma Points
						To specify the subreddit you want to scrape use --subreddit key.
						""")
						
	parser.add_argument('--subreddit', '-s', default="MakingaMurderer", 
						type=str, help="Specify subreddit that you wamt to scrape data from.", 
						nargs=1)
						
	return parser.parse_args()

def gen_target_urls(subreddit):
	base_url = "https://www.reddit.com/r/" + subreddit
	dirs = ["/new/", 
			"/top/", 
			"/top/?sort=top&t=year", 
			"/top/?sort=top&t=month", 
			"/top/?sort=top&t=week",
			"/controversial/", 
			"/controversial/?sort=controversial&t=year", 
			"/controversial/?sort=controversial&t=month",
			"/controversial/?sort=controversial&t=week"
	]
	targets = []
	for dir_ in dirs:
		targets.append(base_url + dir_)
	return targets

def save_results_to_excel(headers, items, filename):
	wb = Workbook()
	ws = wb.active
	ws.append(headers)
	for i in items:
		ws.append(i)
	wb.save(filename)


class PostSpider(Spider):
	
	initial_urls = []

	def prepare(self):
		self.posts_unique_sequences = set()
		self.comments_unique_sequences = set()
		self.posts = set()
		self.comments = set()
	
	# Gets all links to each single post from initial page.
	# Adds link to next page to this initial task.
	def task_initial(self, grab, task):
		
		selector = '//div[@class="entry unvoted"]/ul/li[@class="first"]/a[contains(@class,"comments")]'
		for post in grab.doc.select(selector):
			post_link = grab.make_url_absolute(post.attr("href"))
			grab_custom = Grab()
			grab_custom.setup(
				user_agent="User-agent:Linux:Subreddits-Scraper:1.0 by /u/kadze_yukii", 
				url=post_link
				)
			self.add_task(Task('post',grab=grab_custom))
			
		try:
			next_page = grab.make_url_absolute(grab.doc.select('//a[@rel="nofollow next"]').attr("href"))
			self.add_task(Task('initial', url=next_page))
		except:pass
	
	# Gets all required information for each post.
	# Finds out if there are some comments for a post, if yes, gets the link to all comments.
	def task_post(self, grab, task):
		
		post_title = grab.doc.select('//a[@class="title may-blank "]')[0].text()
		
		dt = grab.doc.select('//div[@id="siteTable"]/div/div/p[@class="tagline"]/time')[0].attr('title')
		post_dt = " ".join(dt.split()[1:])
		
		posted_by = grab.doc.select('//p[@class="tagline"]/a[contains(@class, "author")]')[0].text()
		
		try:
			text_num_comments = grab.doc.select('//a[@class="bylink comments may-blank"]')[0].text()
			num_comments = ''.join([c for c in text_num_comments if c.isnumeric()])
		except:
			num_comments = "0"
			
		karma_points = grab.doc.select('//div[@class="score unvoted"]')[0].text()
		
		ups = grab.doc.select('//div[@class="score"]')[0].text()
		pre_upvote = ups.split('(')[-1]
		upvote = ''.join([c for c in pre_upvote if c.isnumeric()]) + "%"
				
		post = (post_title, post_dt, posted_by, num_comments, karma_points, upvote)
		
		# Filter duplicates: post is unique if its title, post date and author combined together
		# is a unique sequence. 
		post_unique_seq = post[:3]
		if not post_unique_seq in self.posts_unique_sequences:
			self.posts.add(post)
			self.posts_unique_sequences.add(post_unique_seq)
			
		print("%d posts loaded." % len(self.posts))
		
		try:
			all_comments = grab.doc.select('//div[@class="commentarea"]/div/a').attr("href")
			all_comments_link = grab.make_url_absolute(all_comments)
		except:
			all_comments_link = task.url
		
		try:
			no_comments = grab.doc.select('//p[@id="noresults"]')[0].text()
		except:
			self.add_task(Task('post_comments', url=all_comments_link, post=post_title, author=posted_by))
	
	# Gets all required information for every comment of a single post.
	def task_post_comments(self, grab, task):
		
		for comment in grab.doc.select('//div[@data-type="comment"]'):
			post_commented = task.post
			original_poster = task.author
			commenter = comment.attr("data-author")
			dt = comment.select('./div/p[@class="tagline"]/time')[0].attr('title')
			comment_dt = " ".join(dt.split()[1:])
			text_replies = comment.select('./div/p[@class="tagline"]/a[@class="numchildren"]')[0].text()
			num_replies = ''.join([c for c in text_replies.split()[0] if c .isnumeric()])
			try:
				karma_points = comment.select('./div/p[@class="tagline"]/span[@class="score unvoted"]')[0].text()
				karma_points = karma_points.split()[0]
			except:
				karma_points = "1"
				
			comment = (post_commented, original_poster, commenter, comment_dt, num_replies, karma_points)
			
			# Filter duplicates: a comment is not a duplicate if its original post, poster, 
			# commenter and date combined together is a unique sequence.
			comment_unique_seq = comment[:4]
			if not comment_unique_seq in self.comments_unique_sequences:
				self.comments.add(comment)
				self.comments_unique_sequences.add(comment_unique_seq)

if __name__ == '__main__':
	
	args = parse_args()
	subreddit = args.subreddit[0]
	print("Subreddit: ", subreddit)
		
	target_urls = gen_target_urls(subreddit)
		
	bot = PostSpider(thread_number=8)
	bot.initial_urls = target_urls
	bot.run()
	print("DONE.")
	print("%d posts loaded." % len(bot.posts))
	print("%d comments." % len(bot.comments))
	
	post_filename = subreddit + "_posts.xlsx"
	comments_filename = subreddit + "_comments.xlsx"
	
	save_results_to_excel(post_headers, bot.posts, post_filename)
	save_results_to_excel(comment_headers, bot.comments, comments_filename)
	print("Results are saved.")
